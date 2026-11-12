"""Convert the project's 42-case E2E specification to the live runner format."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = (HERE.parents[1] / "MathCheck_E2E_TestSet_v1" / "MathCheck_E2E_TestSet_v1"
          / "MathCheck_E2E_Bench_v1.json")
ACTION_MAP = {
    "parse_search": "search",
    "verify_candidate": "verify",
    "verify_minimize_reverify": "verify",
    "clarify_before_search": "clarify",
    "unsupported": "unsupported",
}


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    cases, expectations, excluded = [], [], []
    for row in source["cases"]:
        expected = row["expected"]
        fixtures = row.get("fixtures", {})
        if fixtures.get("backend_fault"):
            excluded.append({"id": row["case_id"], "reason": "requires fault injection, not supported by the live runner"})
            continue

        action = ACTION_MAP.get(expected.get("action"))
        if action is None:
            raise ValueError(f"Unsupported expected action in {row['case_id']}: {expected.get('action')!r}")
        case = {"id": row["case_id"], "user_input": row["user_input"]}
        if fixtures.get("candidate_graph") is not None:
            case["candidate_graph"] = fixtures["candidate_graph"]
        cases.append(case)

        score_row = {
            "id": row["case_id"],
            "action": action,
            "status": expected["status"],
            "manual_required": True,
        }
        if expected.get("normalized_task") is not None:
            score_row["task"] = expected["normalized_task"]
            if (score_row["status"] == "no_counterexample_in_scope"
                    and expected["normalized_task"].get("search_mode", "exhaustive") == "exhaustive"):
                # The Skill protocol distinguishes completed exhaustive truth from a bounded miss.
                score_row["status"] = "verified_true_in_scope"
        if action == "verify":
            score_row["require_minimization"] = expected["action"] == "verify_minimize_reverify"
        expectations.append(score_row)

    (HERE / "cases.json").write_text(json.dumps({
        "description": "Converted from MathCheck-E2E-Bench v1.0.0; fault-injection cases are listed in exclusions.json.",
        "cases": cases,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "expectations.json").write_text(json.dumps({
        "description": "Frozen expectations converted from MathCheck-E2E-Bench v1.0.0.",
        "cases": expectations,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "exclusions.json").write_text(json.dumps({
        "source": str(SOURCE),
        "excluded": excluded,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(cases)} runnable cases; excluded {len(excluded)} fault-injection cases.")


if __name__ == "__main__":
    main()
