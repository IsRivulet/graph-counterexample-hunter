#!/usr/bin/env python3
"""Evaluate search results against independently built gold labels."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mathcheck.search import search_task

BENCH = Path(__file__).resolve().parent
try:
    from .validation import verify_witness
except ImportError:  # direct script invocation
    from validation import verify_witness


def load(name):
    return json.loads((BENCH / name).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train", "validation", "test", "all"], default="test")
    parser.add_argument("--mode", choices=["exhaustive", "random", "special"], default="exhaustive")
    parser.add_argument("--budget", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    dataset = load("tasks.json")
    gold = {x["task_id"]: x for x in load("ground_truth.json")["cases"]}
    selected = [t for t in dataset["tasks"] if args.split == "all" or t["split"] == args.split]
    rows, missed, false_ids, invalid_ids, contradictory_ids = [], [], [], [], []
    gold_positive = detected_positive = false_count = valid_count = invalid_count = 0
    total_examined = 0
    total_elapsed = 0.0
    for original in selected:
        task = dict(original)
        task.pop("task_id", None); task.pop("split", None)
        task["search_mode"] = args.mode
        if args.mode == "random":
            task["max_graphs"] = args.budget
            task["seed"] = args.seed + int(original["task_id"][2:])
        result = search_task(task)
        truth = gold[original["task_id"]]["counterexample"] is not None
        gold_positive += int(truth)
        found = result["status"] == "counterexample_found"
        verification = verify_witness(task, result.get("counterexample")) if found else None
        valid = bool(verification and verification["valid"])
        if found:
            if valid:
                valid_count += 1
            else:
                invalid_count += 1
                false_count += 1
                invalid_ids.append(original["task_id"])
                false_ids.append(original["task_id"])
            if truth and valid:
                detected_positive += 1
            if truth and not valid:
                missed.append(original["task_id"])
            if not truth:
                false_count += int(valid)
                if valid:
                    false_ids.append(original["task_id"])
                    contradictory_ids.append(original["task_id"])
        elif truth:
            missed.append(original["task_id"])
        coverage = result.get("coverage") or {}
        total_examined += coverage.get("graphs_examined", 0)
        total_elapsed += coverage.get("elapsed_seconds", 0.0)
        rows.append({"task_id": original["task_id"], "split": original["split"],
                     "gold_has_counterexample": truth, "predicted_status": result["status"],
                     "counterexample_found": found, "returned_counterexample_verified": valid if found else None,
                     "verification": verification, "graphs_examined": coverage.get("graphs_examined"),
                     "seed": coverage.get("seed"), "elapsed_seconds": coverage.get("elapsed_seconds")})
    count = len(selected)
    summary = {"benchmark": dataset["benchmark"], "version": dataset["version"], "split": args.split,
        "search_mode": args.mode, "task_count": count, "gold_positive_cases": gold_positive,
        "counterexample_detection_rate": detected_positive / gold_positive if gold_positive else None,
        "detected_gold_counterexamples": detected_positive, "missed_gold_counterexample_ids": missed,
        "false_counterexample_count": false_count, "false_counterexample_ids": false_ids,
        "invalid_returned_counterexample_count": invalid_count, "invalid_returned_counterexample_ids": invalid_ids,
        "gold_contradiction_count": len(contradictory_ids), "gold_contradiction_ids": contradictory_ids,
        "returned_counterexample_verification_rate": valid_count / sum(r["counterexample_found"] for r in rows) if any(r["counterexample_found"] for r in rows) else None,
        "average_graphs_examined": total_examined / count if count else None,
        "total_elapsed_seconds": round(total_elapsed, 6),
        "notes": [
            "A random/special search that finds nothing is not evidence that no counterexample exists.",
            "Ground-truth labels refer only to the finite vertex range specified by each task.",
            "The exhaustive mode is expected to match the reference labels; it is a sanity baseline rather than an efficiency win.",
        ], "per_task": rows}
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output == "-": print(payload)
    else:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        print("Wrote " + args.output)


if __name__ == "__main__":
    main()
