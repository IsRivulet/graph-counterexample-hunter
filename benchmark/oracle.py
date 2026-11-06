"""Independent reference implementation used only to build/evaluate benchmark gold labels.

This intentionally does not import MathCheck's production predicate implementation.
"""

from collections import deque
from itertools import combinations


def reference_predicate(nodes, edges, name, k=None):
    adj = {v: set() for v in nodes}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    degrees = {v: len(adj[v]) for v in nodes}

    if name == "connected":
        seen = {nodes[0]}
        queue = deque([nodes[0]])
        while queue:
            u = queue.popleft()
            for v in adj[u] - seen:
                seen.add(v)
                queue.append(v)
        return len(seen) == len(nodes)

    if name == "bipartite":
        colors = {}
        for root in nodes:
            if root in colors:
                continue
            colors[root] = 0
            queue = deque([root])
            while queue:
                u = queue.popleft()
                for v in adj[u]:
                    if v not in colors:
                        colors[v] = 1 - colors[u]
                        queue.append(v)
                    elif colors[u] == colors[v]:
                        return False
        return True

    # Independent cycle check via DFS parent tracking (not production union-find).
    cycle_found = False
    visited = set()
    for root in nodes:
        if root in visited:
            continue
        stack = [(root, None)]
        while stack:
            u, parent = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            for v in adj[u]:
                if v == parent:
                    continue
                if v in visited:
                    cycle_found = True
                else:
                    stack.append((v, u))

    connected = reference_predicate(nodes, edges, "connected")
    odd_count = sum(d % 2 for d in degrees.values())
    if name == "tree":
        return connected and len(edges) == len(nodes) - 1
    if name == "eulerian_circuit":
        return connected and odd_count == 0
    if name == "eulerian_trail":
        return connected and odd_count in (0, 2)
    if name == "all_even_degree":
        return odd_count == 0
    if name == "has_leaf":
        return any(d == 1 for d in degrees.values())
    if name == "max_degree_at_most_2":
        return all(d <= 2 for d in degrees.values())
    if name == "has_cycle":
        return cycle_found
    if name == "complete":
        return len(edges) == len(nodes) * (len(nodes) - 1) // 2
    if name == "min_degree_at_least_1":
        return all(d >= 1 for d in degrees.values())
    if name == "max_degree_at_most":
        return all(d <= k for d in degrees.values())
    if name == "min_degree_at_least":
        return all(d >= k for d in degrees.values())
    if name == "num_leaves_at_least":
        return sum(1 for d in degrees.values() if d == 1) >= k
    if name == "chromatic_number_at_most":
        return _reference_chromatic(nodes, edges, k)
    if name == "diameter_at_most":
        return _reference_diameter(nodes, edges, k)
    raise ValueError("unknown oracle predicate: " + name)


def _reference_chromatic(nodes, edges, k):
    """Independent k-colorability check via backtracking."""
    if k < 1:
        return not nodes
    adj = {v: set() for v in nodes}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    order = sorted(nodes, key=lambda v: -len(adj[v]))
    color = {}

    def backtrack(idx):
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


def _reference_diameter(nodes, edges, k):
    """Independent diameter check (requires connectivity)."""
    adj = {v: set() for v in nodes}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    # connectivity
    seen = {nodes[0]}
    queue = deque([nodes[0]])
    while queue:
        u = queue.popleft()
        for v in adj[u] - seen:
            seen.add(v)
            queue.append(v)
    if len(seen) != len(nodes):
        return False
    for src in nodes:
        dist = {src: 0}
        q = deque([src])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
        if max(dist.values()) > k:
            return False
    return True


def reference_expr(nodes, edges, expression):
    """Evaluate raw benchmark expressions without production normalization."""
    if isinstance(expression, str):
        return reference_predicate(nodes, edges, expression)
    if "or" in expression:
        value = any(reference_expr(nodes, edges, item) for item in expression["or"])
    else:
        value = reference_predicate(nodes, edges, expression["predicate"], expression.get("k"))
    return not value if expression.get("negated", False) else value


def reference_counterexample(nodes, edges, premises, conclusion):
    import json
    premise_values = {(p if isinstance(p, str) else json.dumps(p, sort_keys=True)): reference_expr(nodes, edges, p) for p in premises}
    conclusion_value = reference_expr(nodes, edges, conclusion)
    return all(premise_values.values()) and not conclusion_value, premise_values, conclusion_value


def reference_graphs(n):
    possible_edges = list(combinations(range(n), 2))
    for mask in range(1 << len(possible_edges)):
        edges = [list(possible_edges[i]) for i in range(len(possible_edges)) if (mask >> i) & 1]
        yield list(range(n)), edges
