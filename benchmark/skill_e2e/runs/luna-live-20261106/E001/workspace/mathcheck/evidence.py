"""Deterministic, inspectable graph certificates and a Mermaid diagram."""
from collections import deque
from .predicates import adjacency


def graph_evidence(graph):
    adj = adjacency(graph)
    components, color, cycle = [], {}, None
    forest = {v: [] for v in graph["nodes"]}
    # An edge closing a forest path supplies a concrete cycle certificate.
    for u, v in graph["edges"]:
        paths = {u: [u]}
        queue = deque([u])
        while queue and v not in paths:
            x = queue.popleft()
            for y in forest[x]:
                if y not in paths:
                    paths[y] = paths[x] + [y]
                    queue.append(y)
        if v in paths:
            if cycle is None:
                cycle = paths[v] + [u]
        else:
            forest[u].append(v)
            forest[v].append(u)
    seen = set()
    bipartite = True
    for start in graph["nodes"]:
        if start in seen:
            continue
        component = []
        queue = deque([start])
        seen.add(start)
        color[start] = 0
        while queue:
            u = queue.popleft()
            component.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    bipartite = False
        components.append(sorted(component))
    ids = {v: "v" + str(i) for i, v in enumerate(graph["nodes"])}
    lines = ["graph LR"]
    lines += ['  %s["%s"]' % (ids[v], v) for v in graph["nodes"]]
    lines += ["  %s --- %s" % (ids[u], ids[v]) for u, v in graph["edges"]]
    return {
        "degrees": {str(v): len(adj[v]) for v in graph["nodes"]},
        "components": components,
        "bipartition": [[v for v in graph["nodes"] if color[v] == c] for c in (0, 1)] if bipartite else None,
        "cycle": cycle,
        "odd_degree_vertices": [v for v in graph["nodes"] if len(adj[v]) % 2],
        "leaves": [v for v in graph["nodes"] if len(adj[v]) == 1],
        "node_count": len(adj), "edge_count": len(graph["edges"]),
        "mermaid": "\n".join(lines),
    }
