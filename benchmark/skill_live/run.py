"""Replay recorded model decisions; does not parse or generate model responses."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mathcheck.search import search_task
from mathcheck.verify import verify_candidate
from mathcheck.minimize import minimize_counterexample
from benchmark.validation import verify_witness
HERE = Path(__file__).resolve().parent

def main():
    data = json.loads((HERE / "responses.json").read_text(encoding="utf-8"))
    rows = []
    for case in data["cases"]:
        response = case["model_response"]
        action = response["action"]
        result = None
        if action == "search":
            result = search_task(response["task"])
        elif action == "verify":
            result = verify_candidate(response["task"], response["graph"])
        row = dict(case, backend_result=result)
        row["expected_outcome_matches"] = action == case["expected_action"] and (result is None or result["status"] == case["expected_status"])
        integrity = []
        if result and result.get("counterexample"):
            witness = result["counterexample"]
            row["reverification"] = verify_witness(response["task"], witness)
            integrity.append(row["reverification"]["valid"])
            reduction = minimize_counterexample(response["task"], witness)
            row["reduction"] = reduction
            reduced = reduction.get("minimized_graph")
            row["reduced_witness_verification"] = verify_witness(response["task"], reduced) if reduced else None
            integrity.append(bool(row["reduced_witness_verification"] and row["reduced_witness_verification"]["valid"]))
        elif action == "verify" and result and response.get("graph"):
            row["reverification"] = verify_witness(response["task"], response["graph"])
            integrity.append(row["reverification"]["valid"] == (result.get("status") == "counterexample_found"))
        row["replay_integrity_pass"] = all(integrity) if integrity else True
        rows.append(row)
    report = {"backend_version": (ROOT / "VERSION").read_text().strip(),
              "evaluation_type": "non_blind_model_response_replay",
              "provenance": data["provenance"], "case_count": len(rows),
              "expected_outcomes_matched": sum(r["expected_outcome_matches"] for r in rows),
              "semantic_parse_match": None, "strict_e2e_pass": None,
              "parse_accuracy": None,
              "replay_integrity_pass": all(r["replay_integrity_pass"] for r in rows),
              "reason": "Historical status replay only; no independent task annotations or actual end-to-end Skill execution.",
              "cases": rows}
    (HERE / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(report["expected_outcomes_matched"]) + "/" + str(len(rows)) + " expected outcomes matched; not an independent Skill accuracy score")
    return 0 if report["replay_integrity_pass"] and all(r["expected_outcome_matches"] for r in rows) else 1

if __name__ == "__main__":
    raise SystemExit(main())
