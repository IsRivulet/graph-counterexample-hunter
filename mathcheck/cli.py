"""Small JSON CLI used by the graph-counterexample-hunter Skill."""

import argparse
import json
import sys
from pathlib import Path

from .minimize import minimize_counterexample
from .search import search_task
from .verify import verify_candidate


def _load_json(path: str):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(data, output: str = "-"):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if output == "-":
        print(payload)
    else:
        Path(output).write_text(payload + "\n", encoding="utf-8")
        # Keep stdout as machine-readable execution evidence even when saving.
        print(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MathCheck finite simple-graph backend")
    sub = parser.add_subparsers(dest="command", required=True)

    search_parser = sub.add_parser("search", help="search for a counterexample")
    search_parser.add_argument("--task", required=True, help="task JSON file, or - for stdin")
    search_parser.add_argument("--output", default="-", help="output JSON file, or - for stdout")
    search_parser.add_argument("--minimize", action="store_true", help="minimize a found counterexample")

    verify_parser = sub.add_parser("verify", help="verify a candidate graph")
    verify_parser.add_argument("--task", required=True)
    verify_parser.add_argument("--graph", required=True)
    verify_parser.add_argument("--output", default="-")

    minimize_parser = sub.add_parser("minimize", help="minimize a verified counterexample")
    minimize_parser.add_argument("--task", required=True)
    minimize_parser.add_argument("--graph", required=True)
    minimize_parser.add_argument("--output", default="-")

    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            task = _load_json(args.task)
            result = search_task(task)
            if args.minimize and result.get("status") == "counterexample_found":
                result["minimization"] = minimize_counterexample(task, result["counterexample"])
                if result.get("minimality", {}).get("vertex_minimum_in_scope"):
                    result["minimization"]["minimality"]["vertex_minimum_in_scope"] = True
                if result["minimization"].get("minimized_graph"):
                    minimized = result["minimization"]["minimized_graph"]
                    # Keep the original verified counterexample field and expose the reduced graph separately.
                    result["minimization"]["verification"] = verify_candidate(task, minimized)
            _write_json(result, args.output)
        elif args.command == "verify":
            _write_json(verify_candidate(_load_json(args.task), _load_json(args.graph)), args.output)
        else:
            _write_json(minimize_counterexample(_load_json(args.task), _load_json(args.graph)), args.output)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("mathcheck error: {0}".format(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
