"""Exhaustive, random, and special-family graph search.

v0.2 additions:
- Exhaustive search reports ``verified_true_in_scope`` (instead of only
  ``no_counterexample_in_scope``) when a full run finds no counterexample,
  because a completed exhaustive search *proves* the proposition in scope.
- Random search deduplicates sampled graphs by isomorphism class (canonical
  form); duplicate samples consume generation budget but skip evaluation.
- Premise/conclusion evaluation uses the normalized expression model
  (parameterized predicates, negation, and disjunction).
"""

import random
import secrets
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Tuple

from .canonical import canonical_key, unlabeled_graph_count
from .graph import all_simple_graphs, normalize_graph, special_graphs
from .predicates import evaluate_task_conditions
from .task import UnsupportedTask, normalize_task


def _coverage(task, fields):
    """Single construction point for shared fields and compatibility aliases."""
    coverage = dict(fields)
    total = None
    if task["search_mode"] == "exhaustive":
        sizes = range(task["min_nodes"], task["max_nodes"] + 1)
        total = sum(1 << (n * (n - 1) // 2) for n in sizes)
        coverage["isomorphism_classes_total"] = sum(unlabeled_graph_count(n) for n in sizes)
    coverage.update({
        "graphs_total": total, "labeled_graphs_total": total,
        "graphs_examined": coverage["graphs_evaluated"],
        "duplicates_skipped": coverage.get("isomorphic_duplicates_skipped", 0),
        "vacuously_true": coverage["premise_satisfying_count"] == 0 if coverage["fully_exhausted"] else None,
    })
    return coverage


def _result(status: str, task: Dict[str, Any], coverage: Dict[str, Any], graph: Any,
            checks: Any, reason: str) -> Dict[str, Any]:
    coverage = _coverage(task, coverage)
    return {
        "status": status,
        "mode": "live",
        "task": task,
        "coverage": coverage,
        "counterexample": graph,
        "checks": checks,
        "minimization": None,
        "reason": reason,
    }


def _check(graph: Dict[str, Any], task: Dict[str, Any]):
    return evaluate_task_conditions(graph, task["normalized_premises"], task["normalized_conclusion"])


def _exhaustive(task: Dict[str, Any]) -> Dict[str, Any]:
    examined = 0
    premise_count = 0
    size_counts = Counter()
    for n in range(task["min_nodes"], task["max_nodes"] + 1):
        for graph in all_simple_graphs(n):
            examined += 1
            size_counts[str(n)] += 1
            checks = _check(graph, task)
            premise_count += int(checks["all_premises_satisfied"])
            if checks["is_counterexample"]:
                coverage = {
                    "search_mode": "exhaustive", "min_nodes": task["min_nodes"], "max_nodes": task["max_nodes"],
                    "graphs_evaluated": examined,
                    "premise_satisfying_count": premise_count,
                    "fully_exhausted": False,
                    "size_counts_examined": dict(size_counts), "seed": None, "max_graphs": None,
                    "termination_reason": "counterexample_found",
                }
                return _result("counterexample_found", task, coverage, graph, checks,
                               "a counterexample was found and passed all predicate checks.")
    coverage = {
        "search_mode": "exhaustive", "min_nodes": task["min_nodes"], "max_nodes": task["max_nodes"],
        "graphs_evaluated": examined,
                    "premise_satisfying_count": premise_count,
        "fully_exhausted": True,
        "size_counts_examined": dict(size_counts), "seed": None, "max_graphs": None,
        "termination_reason": "completed_all_candidates",
    }
    return _result("verified_true_in_scope", task, coverage, None, None,
                   "all simple undirected graphs in the requested vertex range were exhaustively checked; no counterexample exists in scope.")


def _random_graph(n: int, rng: random.Random, p: float) -> Dict[str, Any]:
    from itertools import combinations
    edges = [list(e) for e in combinations(range(n), 2) if rng.random() < p]
    return {"nodes": list(range(n)), "edges": edges}


def _random_search(task: Dict[str, Any]) -> Dict[str, Any]:
    actual_seed = task["seed"] if task["seed"] is not None else secrets.randbits(32)
    rng = random.Random(actual_seed)
    density_schedule = [0.10, 0.25, 0.50, 0.75, 0.90]
    size_counts = Counter()
    density_counts = Counter()
    seen_isomorphism = set()
    duplicate_isomorphic = 0
    premise_count = 0
    for i in range(task["max_graphs"]):
        n = rng.randint(task["min_nodes"], task["max_nodes"])
        p = density_schedule[i % len(density_schedule)]
        graph = _random_graph(n, rng, p)
        # Isomorphism pruning: skip samples that duplicate an already-seen class.
        key = canonical_key(graph)
        if key in seen_isomorphism:
            duplicate_isomorphic += 1
            continue
        seen_isomorphism.add(key)
        checks = _check(graph, task)
        premise_count += int(checks["all_premises_satisfied"])
        size_counts[str(n)] += 1
        density_counts[str(p)] += 1
        if checks["is_counterexample"]:
            coverage = {
                "search_mode": "random", "min_nodes": task["min_nodes"], "max_nodes": task["max_nodes"],
                "samples_generated": i + 1,
                "graphs_evaluated": len(seen_isomorphism), "premise_satisfying_count": premise_count, "fully_exhausted": False,
                "size_counts_examined": dict(size_counts), "density_schedule": density_schedule,
                "density_counts": dict(density_counts), "seed": actual_seed,
                "max_graphs": task["max_graphs"], "termination_reason": "counterexample_found",
                "isomorphic_duplicates_skipped": duplicate_isomorphic,
            }
            return _result("counterexample_found", task, coverage, graph, checks,
                           "a counterexample was found in the random sample and passed all predicate checks.")
    coverage = {
        "search_mode": "random", "min_nodes": task["min_nodes"], "max_nodes": task["max_nodes"],
        "samples_generated": task["max_graphs"],
        "graphs_evaluated": len(seen_isomorphism), "premise_satisfying_count": premise_count, "fully_exhausted": False,
        "size_counts_examined": dict(size_counts), "density_schedule": density_schedule,
        "density_counts": dict(density_counts), "seed": actual_seed,
        "max_graphs": task["max_graphs"], "termination_reason": "budget_exhausted",
        "isomorphic_duplicates_skipped": duplicate_isomorphic,
    }
    return _result("no_counterexample_in_scope", task, coverage, None, None,
                   "the random-search budget was completed without finding a counterexample; this is sampled evidence, not exhaustive proof.")


def _special_search(task: Dict[str, Any]) -> Dict[str, Any]:
    examined = 0
    premise_count = 0
    size_counts = Counter()
    family_counts = Counter()
    seen = set()
    for n in range(task["min_nodes"], task["max_nodes"] + 1):
        for family, raw_graph in special_graphs(n):
            graph = normalize_graph(raw_graph)
            key = (tuple(graph["nodes"]), tuple(tuple(e) for e in graph["edges"]))
            if key in seen:
                continue
            seen.add(key)
            examined += 1
            size_counts[str(n)] += 1
            family_counts[family] += 1
            checks = _check(graph, task)
            premise_count += int(checks["all_premises_satisfied"])
            if checks["is_counterexample"]:
                coverage = {
                    "search_mode": "special", "min_nodes": task["min_nodes"], "max_nodes": task["max_nodes"],
                    "graphs_evaluated": examined, "premise_satisfying_count": premise_count, "fully_exhausted": False,
                    "size_counts_examined": dict(size_counts), "families_examined": dict(family_counts),
                    "families_available": sorted({name for k in range(task["min_nodes"], task["max_nodes"] + 1) for name, _ in special_graphs(k)}),
                    "seed": None, "max_graphs": None, "termination_reason": "counterexample_found",
                }
                return _result("counterexample_found", task, coverage, graph, checks,
                               "a counterexample was found among the documented special graph families and passed all predicate checks.")
    coverage = {
        "search_mode": "special", "min_nodes": task["min_nodes"], "max_nodes": task["max_nodes"],
        "graphs_evaluated": examined, "premise_satisfying_count": premise_count, "fully_exhausted": False,
        "size_counts_examined": dict(size_counts), "families_examined": dict(family_counts),
        "families_available": sorted({name for k in range(task["min_nodes"], task["max_nodes"] + 1) for name, _ in special_graphs(k)}),
        "seed": None, "max_graphs": None, "termination_reason": "completed_special_families",
    }
    return _result("no_counterexample_in_scope", task, coverage, None, None,
                   "all generated graphs in the documented special-family set were checked; this is not exhaustive over all simple graphs.")


def search_task(raw_task: Dict[str, Any]) -> Dict[str, Any]:
    """Search for a graph satisfying every premise and violating the conclusion."""
    try:
        task = normalize_task(raw_task)
    except UnsupportedTask as exc:
        return {"status": "unsupported", "mode": "live", "task": raw_task, "coverage": None,
                "counterexample": None, "checks": None, "minimization": None, "reason": str(exc)}
    except (TypeError, ValueError) as exc:
        return {"status": "inconclusive", "mode": "live", "task": raw_task, "coverage": None,
                "counterexample": None, "checks": None, "minimization": None,
                "reason": "invalid_task: {0}".format(exc)}

    start = time.perf_counter()
    if task["search_mode"] == "exhaustive":
        result = _exhaustive(task)
    elif task["search_mode"] == "random":
        result = _random_search(task)
    else:
        result = _special_search(task)
    coverage = result["coverage"]
    if result["counterexample"] is not None:
        from .verify import verify_candidate
        verified = verify_candidate(raw_task, result["counterexample"])
        result["checks"] = verified["checks"]
        result["evidence"] = verified["evidence"]
        result["minimality"] = {
            "vertex_minimum_in_scope": task["search_mode"] == "exhaustive",
            "edge_minimum_at_minimum_vertices": False,
            "scope": [task["min_nodes"], task["max_nodes"]],
            "reason": "Increasing-size exhaustive enumeration excludes every smaller order in scope." if task["search_mode"] == "exhaustive" else "No exhaustive minimality evidence."
        }
    if coverage["vacuously_true"]:
        result["reason"] += " No graph in scope satisfies all premises (vacuous truth)."
    result["coverage"]["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    return result
