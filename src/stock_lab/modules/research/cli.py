import argparse
import json
import sys

from .backtest import run_backtest
from .context import ResearchConfigurationError, ResearchExecutionError, ResearchSafetyError
from .providers import OfflineResearchProvider, configured_local_context
from .strategies import discover_strategies, get_strategy, validate_target_date


def _add_provider_arguments(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--offline", action="store_true")
    group.add_argument("--provider", choices=("local",), default="local")
    parser.add_argument("--fixture")


def _provider_factory(args):
    if args.fixture and not args.offline:
        raise ResearchConfigurationError("--fixture requires --offline")
    if args.offline:
        provider = (
            OfflineResearchProvider.from_json(args.fixture)
            if args.fixture
            else OfflineResearchProvider.builtin()
        )
        return provider.context
    return configured_local_context


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def main(argv=None, context=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m stock_lab.modules.research")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("identifier")
    run_parser.add_argument("--target-date", type=int, required=True)
    _add_provider_arguments(run_parser)

    backtest_parser = subparsers.add_parser("backtest")
    backtest_parser.add_argument("identifier")
    backtest_parser.add_argument("--start-date", type=int, required=True)
    backtest_parser.add_argument("--end-date", type=int, required=True)
    _add_provider_arguments(backtest_parser)

    args = parser.parse_args(argv)
    if args.command == "list":
        for entry in discover_strategies():
            capabilities = ",".join(entry.metadata.capabilities)
            print(
                f"{entry.identifier}\t{entry.display_name}\t{entry.metadata.adapter_family}"
                f"\t{entry.metadata.entrypoint or '-'}\t{capabilities}"
            )
        return 0

    entry = get_strategy(args.identifier)
    if entry is None:
        print(f"unknown strategy: {args.identifier}", file=sys.stderr)
        return 2

    try:
        if args.command == "run":
            validate_target_date(args.target_date)
            run_context = context.for_target_date(args.target_date) if context else _provider_factory(args)(args.target_date)
            result = entry.run(run_context)
        else:
            validate_target_date(args.start_date)
            validate_target_date(args.end_date)
            if args.start_date > args.end_date:
                raise ResearchConfigurationError("start_date must not be after end_date")
            context_factory = (
                context.for_target_date if context
                else _provider_factory(args)
            )
            result = run_backtest(entry, context_factory, args.start_date, args.end_date)
        print(json.dumps(result.to_dict(), ensure_ascii=False, default=_json_default))
    except (ResearchSafetyError, ResearchConfigurationError, ResearchExecutionError, ImportError, OSError, ValueError) as error:
        print(f"research configuration/execution error: {error}", file=sys.stderr)
        return 2
    return 0
