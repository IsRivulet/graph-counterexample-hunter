"""Deterministic predicates and predicate expressions supported by MathCheck.

A *predicate expression* (``PredExpr``) is the unit used in task ``premises``
and ``conclusion``. It supports three capabilities on top of the v0.1
whitelist:

1. **Parameterized predicates** — degree-family predicates that previously
   hard-coded a threshold now accept an integer argument, e.g.
   ``{"predicate": "max_degree_at_most", "k": 2}``.
2. **Negation** — any predicate may be wrapped as ``{"predicate": ..., "negated": true}``.
3. **Disjunction** — a premise may be an ``OR`` group, e.g.
   ``{"or": [{"predicate": "tree"}, {"predicate": "complete"}]}``.

For backward compatibility, a bare string ``"tree"`` is still accepted and is
treated as ``{"predicate": "tree", "negated": false}``.
"""

from collections import deque
from typing import Any, Dict, List, Set, Union

# --- Predicate metadata -----------------------------------------------------

# A predicate spec: number of required integer arguments.
PARAMETERIZED = {
    "max_degree_at_most": 1,
    "min_degree_at_least": 1,
    "num_leaves_at_least": 1,
    "chromatic_number_at_most": 1,
    "diameter_at_most": 1,
}

# Zero-argument (boolean) predicates. Backward-compatible aliases are resolved
# elsewhere so that the canonical set of zero-arg predicates is explicit.
ZERO_ARG = {
    "connected",
    "bipartite",
    "tree",
    "eulerian_circuit",
    "eulerian_trail",
    "all_even_degree",
    "has_leaf",
    "max_degree_at_most_2",
    "has_cycle",
    "complete",
    "min_degree_at_least_1",
}

# Legacy aliases -> canonical parameterized form. Kept for backward
# compatibility with v0.1 tasks.
ALIASES = {
    "max_degree_at_most_2": ("max_degree_at_most", 2),
    "min_degree_at_least_1": ("min_degree_at_least", 1),
}

# Predicates that may be evaluated incrementally during edge-subset generation
# (monotone in the edge set). Used by the exhaustive search to prune early.
MONOTONE_IN_EDGES = {
    "connected", "all_even_degree", "has_leaf", "has_cycle", "complete",
    "min_degree_at_least", "min_degree_at_least_1",
}

PREDICATE_DEFINITIONS = {
    "connected": "Every pair of vertices is joined by a path; a one-vertex graph is connected.",
    "bipartite": "The vertices can be colored with two colors so every edge has differently colored endpoints.",
    "tree": "A connected, acyclic simple undirected graph; equivalently connected with |E| = |V| - 1.",
    "eulerian_circuit": "The graph is connected and every vertex has even degree.",
    "eulerian_trail": "The graph is connected and has either zero or two odd-degree vertices.",
    "all_even_degree": "Every vertex has even degree, regardless of connectivity.",
    "has_leaf": "At least one vertex has degree exactly one.",
    "has_cycle": "The graph contains at least one undirected cycle.",
    "complete": "Every pair of distinct vertices is joined by an edge.",
    "max_degree_at_most": "Every vertex has degree at most k.",
    "min_degree_at_least": "Every vertex has degree at least k.",
    "num_leaves_at_least": "At least k vertices have degree exactly one.",
    "chromatic_number_at_most": "The graph is k-colorable.",
    "diameter_at_most": "Every pair of vertices is joined by a path of length at most k; the graph must be connected.",
}

# Backward-compatible name set exposed to callers that expect a flat set of
# strings (e.g. older tests, capability listings).
SUPPORTED_PREDICATES = set(ZERO_ARG) | set(PARAMETERIZED) | set(ALIASES)


# --- Graph helpers ----------------------------------------------------------

def adjacency(graph: Dict[str, Any]) -> Dict[int, List[int]]:
    adj = {v: [] for v in graph["nodes"]}
    for u, v in graph["edges"]:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def degree_map(graph: Dict[str, Any]) -> Dict[int, int]:
    adj = adjacency(graph)
    return {v: len(neighbors) for v, neighbors in adj.items()}


def _is_connected(graph: Dict[str, Any]) -> bool:
    nodes = graph["nodes"]
    if not nodes:
        return False
    adj = adjacency(graph)
    seen = {nodes[0]}
    queue = deque([nodes[0]])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    return len(seen) == len(nodes)


def _is_bipartite(graph: Dict[str, Any]) -> bool:
    adj = adjacency(graph)
    color: Dict[int, int] = {}
    for start in graph["nodes"]:
        if start in color:
            continue
        color[start] = 0
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if v not in color:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    return False
    return True


def _has_cycle(graph: Dict[str, Any]) -> bool:
    """Union-find cycle test for a simple undirected graph."""
    parent = {v: v for v in graph["nodes"]}
    rank = {v: 0 for v in graph["nodes"]}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for u, v in graph["edges"]:
        ru, rv = find(u), find(v)
        if ru == rv:
            return True
        if rank[ru] < rank[rv]:
            ru, rv = rv, ru
        parent[rv] = ru
        if rank[ru] == rank[rv]:
            rank[ru] += 1
    return False


def _chromatic_at_most(graph: Dict[str, Any], k: int) -> bool:
    """Greedy-check whether the graph is k-colorable (exact via backtracking)."""
    if k < 1:
        return not graph["nodes"]
    nodes = graph["nodes"]
    adj = adjacency(graph)
    order = sorted(nodes, key=lambda v: -len(adj[v]))  # largest-degree first
    color: Dict[int, int] = {}

    def backtrack(idx: int) -> bool:
        if idx == len(order):
            return True
        v = order[idx]
        forbidden = {color[u] for u in adj[v] if u in color}
        for c in range(k):
            if c in forbidden:
                continue
            color[v] = c
            if backtrack(idx + 1):
                return True
            del color[v]
        return False

    return backtrack(0)


def _diameter_at_most(graph: Dict[str, Any], k: int) -> bool:
    """True iff the graph is connected and every pair has distance <= k."""
    if not _is_connected(graph):
        return False
    adj = adjacency(graph)
    for src in graph["nodes"]:
        dist = {src: 0}
        queue = deque([src])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    queue.append(v)
        if max(dist.values()) > k:
            return False
    return True


# --- Core evaluation --------------------------------------------------------

def evaluate_atom(graph: Dict[str, Any], predicate: str, k: int = None) -> bool:
    """Evaluate a single (non-negated, non-disjunctive) predicate on ``graph``.

    ``predicate`` must be a canonical name (a key of ``ZERO_ARG`` or
    ``PARAMETERIZED``). Legacy aliases are resolved by the caller via
    ``resolve_alias``.
    """
    nodes = graph["nodes"]
    edges = graph["edges"]
    degrees = degree_map(graph)

    if predicate == "connected":
        return _is_connected(graph)
    if predicate == "bipartite":
        return _is_bipartite(graph)
    if predicate == "tree":
        return _is_connected(graph) and len(edges) == len(nodes) - 1
    if predicate == "eulerian_circuit":
        return _is_connected(graph) and all(d % 2 == 0 for d in degrees.values())
    if predicate == "eulerian_trail":
        odd = sum(1 for d in degrees.values() if d % 2 == 1)
        return _is_connected(graph) and odd in (0, 2)
    if predicate == "all_even_degree":
        return all(d % 2 == 0 for d in degrees.values())
    if predicate == "has_leaf":
        return any(d == 1 for d in degrees.values())
    if predicate == "has_cycle":
        return _has_cycle(graph)
    if predicate == "complete":
        return len(edges) == len(nodes) * (len(nodes) - 1) // 2
    if predicate == "max_degree_at_most":
        return all(d <= k for d in degrees.values())
    if predicate == "min_degree_at_least":
        return all(d >= k for d in degrees.values())
    if predicate == "num_leaves_at_least":
        return sum(1 for d in degrees.values() if d == 1) >= k
    if predicate == "chromatic_number_at_most":
        return _chromatic_at_most(graph, k)
    if predicate == "diameter_at_most":
        return _diameter_at_most(graph, k)

    raise AssertionError("predicate dispatch is incomplete: {0}".format(predicate))


# --- Predicate expression model --------------------------------------------

# A predicate expression is one of:
#   * a bare string, e.g. "tree"
#   * an atom dict: {"predicate": name, "negated": bool, "k": int}
#   * an OR dict:   {"or": [expr, ...], "negated": bool}
PredExpr = Union[str, Dict[str, Any]]


def resolve_alias(predicate: str) -> str:
    if predicate in ALIASES:
        canonical, _ = ALIASES[predicate]
        return canonical
    return predicate


def normalize_expr(expr: PredExpr) -> Dict[str, Any]:
    """Normalize any accepted predicate expression into a canonical dict."""
    if isinstance(expr, str):
        expr = {"predicate": expr}
    if not isinstance(expr, dict):
        raise ValueError("predicate expression must be a string or object.")

    if "or" in expr:
        alternatives = expr["or"]
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError("an OR predicate must contain a non-empty list of alternatives.")
        return {
            "type": "or",
            "negated": bool(expr.get("negated", False)),
            "alternatives": [normalize_expr(a) for a in alternatives],
        }

    name = expr.get("predicate")
    if not isinstance(name, str):
        raise ValueError("an atom predicate requires a string 'predicate' name.")

    canonical = resolve_alias(name)
    known = canonical in ZERO_ARG or canonical in PARAMETERIZED
    if not known:
        raise ValueError("unsupported predicate: {0}".format(name))

    # Resolve legacy alias defaults first: max_degree_at_most_2 -> (max_degree_at_most, 2).
    k = expr.get("k")
    if name in ALIASES and k is None:
        _, default_k = ALIASES[name]
        k = default_k

    if canonical in PARAMETERIZED:
        if not isinstance(k, int) or isinstance(k, bool):
            raise ValueError("predicate '{0}' requires an integer 'k'.".format(name))
        if k < 1:
            raise ValueError("predicate '{0}' requires k >= 1.".format(name))
    elif "k" in expr:
        raise ValueError("predicate '{0}' does not accept a 'k' argument.".format(name))

    negated = bool(expr.get("negated", False))
    return {"type": "atom", "predicate": canonical, "negated": negated, "k": k}


def expr_names(expr: Dict[str, Any]) -> Set[str]:
    """Collect all canonical predicate names referenced by a normalized expr."""
    if expr["type"] == "atom":
        return {expr["predicate"]}
    return set().union(*[expr_names(a) for a in expr["alternatives"]])


def evaluate_expr(graph: Dict[str, Any], expr: Dict[str, Any]) -> bool:
    """Evaluate a normalized predicate expression to a boolean."""
    if expr["type"] == "atom":
        value = evaluate_atom(graph, expr["predicate"], expr["k"])
        return (not value) if expr["negated"] else value
    # OR group.
    value = any(evaluate_expr(graph, a) for a in expr["alternatives"])
    return (not value) if expr["negated"] else value


def normalize_conditions(raw_premises: List[PredExpr], raw_conclusion: PredExpr):
    """Normalize premises (list of expressions) and conclusion (one expression)."""
    if not isinstance(raw_premises, list) or any(not isinstance(p, (str, dict)) for p in raw_premises):
        raise ValueError("premises must be an array of predicate names or objects.")
    premises = [normalize_expr(p) for p in raw_premises]
    if not isinstance(raw_conclusion, (str, dict)):
        raise ValueError("conclusion must be one predicate name or object.")
    conclusion = normalize_expr(raw_conclusion)
    return premises, conclusion


# --- Backward-compatible string API ----------------------------------------

def evaluate_predicate(graph: Dict[str, Any], predicate: str) -> bool:
    """Evaluate a legacy string predicate (kept for v0.1 callers and tests).

    Supports both canonical parameterized names (requiring ``k`` is not
    possible here, so only zero-arg names and aliases are supported) and the
    legacy alias names.
    """
    if predicate not in SUPPORTED_PREDICATES:
        raise ValueError("unsupported predicate: {0}".format(predicate))
    canonical = resolve_alias(predicate)
    k = None
    if predicate in ALIASES:
        _, k = ALIASES[predicate]
    return evaluate_atom(graph, canonical, k)


def evaluate_task_conditions(graph: Dict[str, Any], premises: List[PredExpr], conclusion: PredExpr) -> Dict[str, Any]:
    """Evaluate premises and conclusion.

    ``premises`` and ``conclusion`` must already be *normalized* expressions
    (the output of ``normalize_conditions``). If you hold raw task fields, call
    ``normalize_conditions`` first.
    """
    premise_checks = [
        {"index": i, "expression": expr, "label": _expr_key(expr),
         "value": evaluate_expr(graph, expr)}
        for i, expr in enumerate(premises)
    ]
    # Compatibility display map; logical decisions use the lossless list.
    premise_results = {item["label"]: item["value"] for item in premise_checks}
    conclusion_value = evaluate_expr(graph, conclusion)
    is_counterexample = all(item["value"] for item in premise_checks) and not conclusion_value
    return {
        "premises": premise_results,
        "premise_checks": premise_checks,
        "all_premises_satisfied": all(item["value"] for item in premise_checks),
        "conclusion_value": conclusion_value,
        "conclusion": {_expr_key(conclusion): conclusion_value},
        "is_counterexample": is_counterexample,
    }


def _expr_key(expr: Dict[str, Any]) -> str:
    """A stable, human-readable key for a *normalized* predicate expression."""
    if expr.get("type") == "or":
        inner = " or ".join(_expr_key(a) for a in expr["alternatives"])
        key = "({0})".format(inner)
        return "not {0}".format(key) if expr.get("negated") else key
    name = expr.get("predicate")
    if expr.get("k") is not None:
        name = "{0}({1})".format(name, expr.get("k"))
    return "not {0}".format(name) if expr.get("negated") else name
