"""Graph input validation and deterministic graph constructors."""

from itertools import combinations
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple


class GraphInputError(ValueError):
    pass


def normalize_graph(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a simple undirected graph using integer node IDs."""
    if not isinstance(raw, dict):
        raise GraphInputError("graph must be a JSON object with 'nodes' and 'edges'.")
    nodes = raw.get("nodes")
    edges = raw.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise GraphInputError("graph.nodes and graph.edges must both be arrays.")
    if not nodes:
        raise GraphInputError("empty graphs are not supported; use at least one vertex.")
    if any(not isinstance(v, int) or isinstance(v, bool) for v in nodes):
        raise GraphInputError("all vertex labels must be integers (booleans are not accepted).")
    if len(set(nodes)) != len(nodes):
        raise GraphInputError("graph.nodes contains duplicate vertex labels.")

    node_set = set(nodes)
    normalized_edges: List[List[int]] = []
    seen = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise GraphInputError("edge at index {0} must contain exactly two endpoints.".format(index))
        u, v = edge
        if not isinstance(u, int) or isinstance(u, bool) or not isinstance(v, int) or isinstance(v, bool):
            raise GraphInputError("edge endpoints must be integer vertex labels.")
        if u not in node_set or v not in node_set:
            raise GraphInputError("edge {0} references a vertex absent from graph.nodes.".format(edge))
        if u == v:
            raise GraphInputError("self-loops are not allowed in a simple undirected graph.")
        key = (min(u, v), max(u, v))
        if key in seen:
            raise GraphInputError("duplicate undirected edge: {0}.".format(list(key)))
        seen.add(key)
        normalized_edges.append([key[0], key[1]])

    normalized_edges.sort()
    normalized_nodes = sorted(nodes)
    return {"nodes": normalized_nodes, "edges": normalized_edges}


def graph_from_edges(n: int, edges: Iterable[Tuple[int, int]]) -> Dict[str, Any]:
    return normalize_graph({"nodes": list(range(n)), "edges": [list(e) for e in edges]})


def all_simple_graphs(n: int) -> Iterator[Dict[str, Any]]:
    """Enumerate every labeled simple undirected graph on vertices 0..n-1.

    Order is deterministic: edge subsets are visited by increasing bit mask.
    """
    if n < 1:
        return
    possible = list(combinations(range(n), 2))
    for mask in range(1 << len(possible)):
        edges = [possible[i] for i in range(len(possible)) if (mask >> i) & 1]
        yield {"nodes": list(range(n)), "edges": [list(e) for e in edges]}


def special_graphs(n: int) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield a deterministic, documented collection of common graph families."""
    nodes = list(range(n))
    yield "empty", {"nodes": nodes, "edges": []}
    if n >= 2:
        yield "path", {"nodes": nodes, "edges": [[i, i + 1] for i in range(n - 1)]}
        yield "star", {"nodes": nodes, "edges": [[0, i] for i in range(1, n)]}
        yield "complete_bipartite_balanced", {
            "nodes": nodes,
            "edges": [[u, v] for u in range(n // 2) for v in range(n // 2, n)],
        }
        yield "clique_plus_isolate", {
            "nodes": nodes,
            "edges": [[u, v] for u, v in combinations(range(n - 1), 2)],
        }
    if n >= 3:
        yield "cycle", {"nodes": nodes, "edges": [[i, (i + 1) % n] for i in range(n)]}
        yield "complete", {"nodes": nodes, "edges": [list(e) for e in combinations(nodes, 2)]}
    if n >= 4:
        cycle_edges = [[i, (i + 1) % (n - 1)] for i in range(n - 1)]
        cycle_edges.append([0, n - 1])
        yield "cycle_with_leaf", {"nodes": nodes, "edges": cycle_edges}
    if n >= 6 and n % 2 == 0:
        half = n // 2
        edges = []
        for start in (0, half):
            edges.extend([[start + i, start + ((i + 1) % half)] for i in range(half)])
        yield "two_disjoint_cycles", {"nodes": nodes, "edges": edges}
