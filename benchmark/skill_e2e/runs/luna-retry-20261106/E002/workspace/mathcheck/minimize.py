"""Greedy counterexample reduction; does not claim global minimality."""

from typing import Any, Dict, List

from .graph import normalize_graph
from .verify import verify_candidate


def _relabel(graph: Dict[str, Any]) -> Dict[str, Any]:
    nodes = graph["nodes"]
    mapping = {old: new for new, old in enumerate(nodes)}
    edges = [[mapping[u], mapping[v]] for u, v in graph["edges"]]
    return {"nodes": list(range(len(nodes))), "edges": edges}


def minimize_counterexample(raw_task: Dict[str, Any], raw_graph: Dict[str, Any]) -> Dict[str, Any]:
    """Greedily remove vertices first, then edges, preserving counterexample status."""
    original = normalize_graph(raw_graph)
    initial_verification = verify_candidate(raw_task, original)
    if initial_verification["status"] != "counterexample_found":
        return {
            "status": "rejected_input", "original_graph": original, "minimized_graph": None,
            "original_size": {"nodes": len(original["nodes"]), "edges": len(original["edges"])},
            "minimized_size": None, "steps": [], "verification": initial_verification,
            "minimality_claim": None,
            "reason": "input graph did not pass the MathCheck counterexample verifier.",
        }

    task = dict(raw_task)
    task.setdefault("search_mode", "exhaustive")
    current = original
    steps: List[Dict[str, Any]] = []
    changed = True
    while changed:
        changed = False
        # First try deleting vertices, as specified by the Skill's lexicographic preference.
        if len(current["nodes"]) > task.get("min_nodes", 1):
            for vertex in list(current["nodes"]):
                if len(current["nodes"]) - 1 < task.get("min_nodes", 1):
                    break
                nodes = [v for v in current["nodes"] if v != vertex]
                edges = [[u, v] for u, v in current["edges"] if u != vertex and v != vertex]
                candidate = _relabel({"nodes": nodes, "edges": edges})
                result = verify_candidate(task, candidate)
                if result["status"] == "counterexample_found":
                    steps.append({"operation": "delete_vertex", "removed_vertex": vertex,
                                  "before": {"nodes": len(current["nodes"]), "edges": len(current["edges"])},
                                  "after": {"nodes": len(candidate["nodes"]), "edges": len(candidate["edges"])}})
                    current = candidate
                    changed = True
                    break
        if changed:
            continue
        # Then try deleting edges one at a time.
        for edge in list(current["edges"]):
            edges = [e for e in current["edges"] if e != edge]
            candidate = {"nodes": current["nodes"][:], "edges": edges}
            result = verify_candidate(task, candidate)
            if result["status"] == "counterexample_found":
                steps.append({"operation": "delete_edge", "removed_edge": edge,
                              "before": {"nodes": len(current["nodes"]), "edges": len(current["edges"])},
                              "after": {"nodes": len(candidate["nodes"]), "edges": len(candidate["edges"])}})
                current = candidate
                changed = True
                break

    final_verification = verify_candidate(task, current)
    return {
        "status": "minimized" if current != original else "no_improvement",
        "original_graph": original,
        "minimized_graph": current,
        "original_size": {"nodes": len(original["nodes"]), "edges": len(original["edges"])},
        "minimized_size": {"nodes": len(current["nodes"]), "edges": len(current["edges"])},
        "steps": steps,
        "verification": final_verification,
        "minimality_claim": "locally_minimal_under_single_vertex_and_edge_deletions",
        "minimality": {"local_single_deletion_minimum": True,
                       "vertex_minimum_in_scope": False,
                       "edge_minimum_at_minimum_vertices": False,
                       "scope": [task.get("min_nodes", 1), task.get("max_nodes", 5)]},
        "reason": "the returned graph was re-verified; local deletion minimality is not a proof of global minimum size.",
    }
