import argparse

from .strategies import discover_strategies, get_strategy


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
            print(f"{entry.identifier}\t{entry.display_name}")
        return 0
    entry = get_strategy(args.identifier)
    if entry is None:
        print(f"unknown strategy: {args.identifier}")
        return 2
    if context is None:
        print("run requires an explicitly injected ResearchContext")
        return 2
    try:
        entry.run(context, target_date=args.target_date)
    except (TypeError, ValueError, KeyError) as error:
        print(f"strategy could not run: {error}")
        return 2
    return 0
