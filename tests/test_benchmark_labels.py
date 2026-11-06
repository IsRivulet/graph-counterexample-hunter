import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mathcheck.search import search_task
from mathcheck.verify import verify_candidate


BENCH = ROOT / "benchmark"


def test_all_benchmark_gold_labels_match_exhaustive_backend():
    dataset = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    gold = {x["task_id"]: x for x in json.loads((BENCH / "ground_truth.json").read_text(encoding="utf-8"))["cases"]}
    for raw in dataset["tasks"]:
        task = {k: v for k, v in raw.items() if k not in ("task_id", "split")}
        result = search_task(task)
        expected_positive = gold[raw["task_id"]]["counterexample"] is not None
        assert (result["status"] == "counterexample_found") == expected_positive, raw["task_id"]
        if not expected_positive:
            assert result["coverage"]["fully_exhausted"] is True
            assert result["coverage"]["vacuously_true"] == gold[raw["task_id"]]["vacuously_true"]
            assert result["coverage"]["premise_satisfying_count"] == gold[raw["task_id"]]["premise_satisfying_count"]


def test_all_verification_cases_match_expected_labels():
    tasks = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    task_map = {x["task_id"]: {k: v for k, v in x.items() if k not in ("task_id", "split")} for x in tasks}
    cases = json.loads((BENCH / "verification_cases.json").read_text(encoding="utf-8"))["cases"]
    for case in cases:
        result = verify_candidate(task_map[case["task_id"]], case["graph"])
        assert (result["status"] == "counterexample_found") == case["expected_is_counterexample"], case["case_id"]
        assert result["checks"]["conclusion_value"] == case["expected_conclusion_value"], case["case_id"]
        assert [item["value"] for item in result["checks"]["premise_checks"]] == list(case["expected_premise_values"].values()), case["case_id"]


def test_candidate_verification_is_not_limited_by_search_mode_cap():
    task = {
        "premises": [], "conclusion": "has_cycle", "min_nodes": 1,
        "max_nodes": 8, "search_mode": "exhaustive",
    }
    graph = {"nodes": list(range(7)), "edges": [[i, i + 1] for i in range(6)]}
    result = verify_candidate(task, graph)
    assert result["status"] == "counterexample_found"
