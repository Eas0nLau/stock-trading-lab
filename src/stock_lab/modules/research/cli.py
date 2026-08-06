import argparse
import sys

from .context import ResearchConfigurationError, ResearchSafetyError
from .strategies import discover_strategies, get_strategy, validate_target_date


def main(argv=None, context=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m stock_lab.modules.research")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("identifier")
    run_parser.add_argument("--target-date", type=int)
    args = parser.parse_args(argv)
    if args.command == "list":
        for entry in discover_strategies():
            capabilities = ",".join(entry.metadata.capabilities)
            print(
                f"{entry.identifier}\t{entry.display_name}\t{entry.metadata.safety_status}"
                f"\t{entry.metadata.entrypoint or '-'}\t{capabilities}"
            )
        return 0
    entry = get_strategy(args.identifier)
    if entry is None:
        print(f"unknown strategy: {args.identifier}")
        return 2
    if context is None:
        print("run requires an explicitly injected ResearchContext", file=sys.stderr)
        return 2
    try:
        if args.target_date is not None:
            validate_target_date(args.target_date)
        run_context = (
            context.with_parameters(target_date=args.target_date)
            if args.target_date is not None
            else context
        )
        entry.run(run_context)
    except (ResearchSafetyError, ResearchConfigurationError, ImportError, OSError) as error:
        print(f"strategy safety/configuration error: {error}", file=sys.stderr)
        return 2
    return 0
