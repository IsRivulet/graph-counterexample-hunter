"""Candidate graph verification."""

from typing import Any, Dict

from .evidence import graph_evidence
from .graph import GraphInputError, normalize_graph
from .predicates import evaluate_task_conditions
from .task import UnsupportedTask, normalize_task


def verify_candidate(raw_task: Dict[str, Any], raw_graph: Dict[str, Any]) -> Dict[str, Any]:
    try:
        task = normalize_task(dict(raw_task, search_mode=raw_task.get("search_mode", "random")), enforce_search_limits=False)
    except UnsupportedTask as exc:
        return {"status": "unsupported", "mode": "live", "task": raw_task, "coverage": None,
                "counterexample": None, "checks": None, "minimization": None, "reason": str(exc)}
    except (TypeError, ValueError) as exc:
        return {"status": "inconclusive", "mode": "live", "task": raw_task, "coverage": None,
                "counterexample": None, "checks": None, "minimization": None, "reason": "invalid_task: {0}".format(exc)}

    try:
        graph = normalize_graph(raw_graph)
    except GraphInputError as exc:
        return {"status": "inconclusive", "mode": "live", "task": task, "coverage": None,
                "counterexample": None, "checks": {"graph_structure_valid": False},
                "minimization": None, "reason": "candidate_rejected: {0}".format(exc)}

    in_range = task["min_nodes"] <= len(graph["nodes"]) <= task["max_nodes"]
    if not in_range:
        return {"status": "inconclusive", "mode": "live", "task": task, "coverage": None,
                "counterexample": None,
                "checks": {"graph_structure_valid": True, "node_count_in_range": False},
                "minimization": None,
                "reason": "candidate_rejected: node count {0} is outside [{1}, {2}].".format(
                    len(graph["nodes"]), task["min_nodes"], task["max_nodes"]) }

    condition_results = evaluate_task_conditions(graph, task["normalized_premises"], task["normalized_conclusion"])
    checks = {
        "graph_structure_valid": True,
        "node_count_in_range": True,
        "premises": condition_results["premises"],
        "conclusion": condition_results["conclusion"],
        "premise_checks": condition_results["premise_checks"],
        "conclusion_value": condition_results["conclusion_value"],
        "all_premises_satisfied": condition_results["all_premises_satisfied"],
        "conclusion_violated": not condition_results["conclusion_value"],
        "is_counterexample": condition_results["is_counterexample"],
    }
    if checks["is_counterexample"]:
        return {"status": "counterexample_found", "mode": "live", "task": task, "coverage": None,
                "counterexample": graph, "checks": checks, "evidence": graph_evidence(graph), "minimization": None,
                "reason": "candidate independently passed graph, range, premise, and conclusion checks."}
    return {"status": "inconclusive", "mode": "live", "task": task, "coverage": None,
            "counterexample": None, "checks": checks, "minimization": None,
            "reason": "candidate_rejected: it is not a counterexample for this task."}
