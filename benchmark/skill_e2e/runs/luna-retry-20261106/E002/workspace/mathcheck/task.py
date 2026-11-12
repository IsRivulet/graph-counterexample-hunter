"""Validation of the MathCheck task format.

Supports the v0.1 flat format (premises/conclusion as bare predicate-name
strings) plus the extended expression format where a premise or the conclusion
may be a predicate object, e.g. ``{"predicate": "max_degree_at_most", "k": 2,
"negated": true}`` or an OR group ``{"or": [...]}``.
"""

from typing import Any, Dict, List

from .predicates import normalize_conditions, expr_names, SUPPORTED_PREDICATES

EXHAUSTIVE_MAX_NODES = 6
RANDOM_SPECIAL_MAX_NODES = 10


class UnsupportedTask(ValueError):
    pass


def normalize_task(raw: Dict[str, Any], enforce_search_limits: bool = True) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("task must be a JSON object.")

    graph_type = raw.get("graph_type", "simple_undirected")
    if graph_type != "simple_undirected":
        raise UnsupportedTask("only graph_type='simple_undirected' is supported.")

    premises = raw.get("premises")
    conclusion = raw.get("conclusion")
    if not isinstance(premises, list) or any(not isinstance(p, (str, dict)) for p in premises):
        raise ValueError("premises must be an array of predicate names or objects.")

    # Normalize premises/conclusion, distinguishing "unsupported" from "malformed".
    try:
        norm_premises, norm_conclusion = normalize_conditions(premises, conclusion)
    except ValueError as exc:
        # Unknown predicate names surface here as "unsupported predicate".
        msg = str(exc)
        if msg.startswith("unsupported predicate"):
            raise UnsupportedTask(msg)
        raise

    # Duplicate detection on the serialized premise expressions.
    premise_keys = [repr(p) for p in norm_premises]
    if len(set(premise_keys)) != len(premise_keys):
        raise ValueError("premises must not contain duplicate predicates.")

    min_nodes = raw.get("min_nodes", 1)
    max_nodes = raw.get("max_nodes", 5)
    if not isinstance(min_nodes, int) or isinstance(min_nodes, bool) or not isinstance(max_nodes, int) or isinstance(max_nodes, bool):
        raise ValueError("min_nodes and max_nodes must be integers.")
    if min_nodes < 1 or max_nodes < min_nodes:
        raise ValueError("require 1 <= min_nodes <= max_nodes.")

    mode = raw.get("search_mode", "exhaustive")
    if mode not in ("exhaustive", "random", "special"):
        raise UnsupportedTask("search_mode must be exhaustive, random, or special.")
    if enforce_search_limits:
        if mode == "exhaustive" and max_nodes > EXHAUSTIVE_MAX_NODES:
            raise UnsupportedTask("exhaustive search is capped at {0} vertices; requested max_nodes={1}.".format(EXHAUSTIVE_MAX_NODES, max_nodes))
        if mode in ("random", "special") and max_nodes > RANDOM_SPECIAL_MAX_NODES:
            raise UnsupportedTask("{0} search is capped at {1} vertices.".format(mode, RANDOM_SPECIAL_MAX_NODES))

    seed = raw.get("seed")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ValueError("seed must be an integer or null.")
    max_graphs = raw.get("max_graphs", 2000)
    if not isinstance(max_graphs, int) or isinstance(max_graphs, bool) or max_graphs < 1:
        raise ValueError("max_graphs must be a positive integer.")

    result = {
        "property_id": raw.get("property_id"),
        "graph_type": graph_type,
        "premises": premises[:],
        "conclusion": conclusion,
        "normalized_premises": norm_premises,
        "normalized_conclusion": norm_conclusion,
        "min_nodes": min_nodes,
        "max_nodes": max_nodes,
        "search_mode": mode,
        "seed": seed,
        "max_graphs": max_graphs,
    }
    if result["property_id"] is not None and not isinstance(result["property_id"], str):
        raise ValueError("property_id must be a string or null.")
    return result
