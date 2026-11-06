#!/usr/bin/env python3
"""Evaluate B's candidate verifier against independent candidate labels."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mathcheck.verify import verify_candidate

BENCH = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train", "validation", "test", "all"], default="all")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    task_records = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    task_map = {t["task_id"]: t for t in task_records}
    cases = json.loads((BENCH / "verification_cases.json").read_text(encoding="utf-8"))["cases"]
    selected = [c for c in cases if args.split == "all" or task_map[c["task_id"]]["split"] == args.split]

    correct = 0
    tp = fp = fn = tn = 0
    rows = []
    for case in selected:
        task = dict(task_map[case["task_id"]])
        task.pop("task_id", None)
        task.pop("split", None)
        result = verify_candidate(task, case["graph"])
        predicted = result["status"] == "counterexample_found"
        expected = case["expected_is_counterexample"]
        correct += int(predicted == expected)
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
        elif not predicted and expected:
            fn += 1
        else:
            tn += 1
        rows.append({"case_id": case["case_id"], "expected": expected, "predicted": predicted,
                     "correct": predicted == expected, "reason": result.get("reason")})

    total = len(selected)
    result = {
        "benchmark": "MathCheck-Bench-Verifier",
        "split": args.split,
        "case_count": total,
        "accuracy": correct / total if total else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "per_case": rows,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(payload)
    else:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        print("Wrote " + args.output)


if __name__ == "__main__":
    main()
