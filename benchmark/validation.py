"""Independent structural and semantic validation for benchmark witnesses."""

try:
    from .oracle import reference_counterexample
except ImportError:  # direct benchmark script execution
    from oracle import reference_counterexample


def verify_witness(task, graph):
    """Validate a simple undirected witness without using production verification."""
    def fail(reason):
        return {"valid": False, "reason": reason, "premise_values": None, "conclusion_value": None}

    if not isinstance(task, dict) or not isinstance(graph, dict):
        return fail("task and graph must be objects")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not nodes:
        return fail("nodes must be a non-empty list")
    if any(type(n) is not int for n in nodes) or len(set(nodes)) != len(nodes):
        return fail("nodes must be unique integers (booleans excluded)")
    lo, hi = task.get("min_nodes", 1), task.get("max_nodes", 5)
    if type(lo) is not int or type(hi) is not int or not lo <= len(nodes) <= hi:
        return fail("node count outside task range")
    if task.get("graph_type", "simple_undirected") != "simple_undirected":
        return fail("unsupported graph type")
    if not isinstance(edges, list):
        return fail("edges must be a list")
    seen = set()
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            return fail("each edge must have two endpoints")
        u, v = edge
        if type(u) is not int or type(v) is not int or u not in nodes or v not in nodes:
            return fail("edge endpoint is not a graph node")
        if u == v:
            return fail("loops are not allowed")
        key = frozenset((u, v))
        if key in seen:
            return fail("duplicate undirected edge")
        seen.add(key)
    try:
        is_ce, premise_values, conclusion_value = reference_counterexample(
            nodes, edges, task.get("premises", []), task["conclusion"])
    except (KeyError, TypeError, ValueError) as exc:
        return fail("oracle evaluation failed: " + str(exc))
    return {"valid": bool(is_ce), "reason": None if is_ce else "premises do not hold or conclusion is not violated",
            "premise_values": premise_values, "conclusion_value": conclusion_value}
