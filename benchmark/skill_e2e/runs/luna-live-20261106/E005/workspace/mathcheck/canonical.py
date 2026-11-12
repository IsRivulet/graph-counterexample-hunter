"""Canonical form for simple undirected graphs (isomorphism pruning).

Provides an isomorphism-invariant key for small graphs. The key is the
lexicographically smallest adjacency matrix (row-major bitmasks) over all
vertex permutations. Two isomorphic graphs always produce the same key, and
two non-isomorphic graphs always produce different keys, so the key is a
faithful canonical form.

This is used by the random search to deduplicate sampled graphs by isomorphism
class, so the sampling budget is not wasted on isomorphic duplicates.
"""

from itertools import permutations
from typing import Any, Dict, Tuple


def _canonical_from_bits(n: int, adj: Tuple[int, ...]) -> Tuple[int, ...]:
    """Lexicographically smallest adjacency matrix over all vertex permutations."""
    best = None
    for perm in permutations(range(n)):
        rows = []
        for i in range(n):
            row = 0
            bits = adj[perm[i]]
            for j in range(n):
                if bits & (1 << perm[j]):
                    row |= (1 << j)
            rows.append(row)
        key = tuple(rows)
        if best is None or key < best:
            best = key
    return best


def canonical_key(graph: Dict[str, Any]) -> Tuple[int, ...]:
    """Return an isomorphism-invariant key for a normalized simple graph.

    ``graph`` is a normalized graph dict with integer nodes 0..n-1 and an
    ``edges`` list. Returns a tuple that is equal for isomorphic graphs and
    different for non-isomorphic graphs.
    """
    nodes = graph["nodes"]
    n = len(nodes)
    if n == 0:
        return ()
    if n == 1:
        return (0,)

    adj = [0] * n
    for u, v in graph["edges"]:
        adj[u] |= (1 << v)
        adj[v] |= (1 << u)
    return _canonical_from_bits(n, tuple(adj))


def unlabeled_graph_count(n: int) -> int:
    """Number of unlabeled simple graphs on n vertices (OEIS A000088)."""
    a000088 = [1, 1, 2, 4, 11, 34, 156, 1044, 12346, 274668, 12005168]
    if n < len(a000088):
        return a000088[n]
    raise ValueError("unlabeled graph count unavailable for n={0}".format(n))
