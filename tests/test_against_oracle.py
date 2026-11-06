import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

from mathcheck.predicates import evaluate_predicate, evaluate_atom
from benchmark.oracle import reference_predicate, reference_graphs


# Zero-argument predicates (and legacy aliases) evaluated via the string API.
ZERO_ARG_AND_ALIASES = [
    "connected", "bipartite", "tree", "eulerian_circuit", "eulerian_trail",
    "all_even_degree", "has_leaf", "max_degree_at_most_2", "has_cycle",
    "complete", "min_degree_at_least_1",
]

# Parameterized predicates with the k values to cross-check.
PARAMETERIZED_CASES = [
    ("max_degree_at_most", 1),
    ("max_degree_at_most", 2),
    ("min_degree_at_least", 1),
    ("min_degree_at_least", 2),
    ("num_leaves_at_least", 1),
    ("num_leaves_at_least", 2),
    ("chromatic_number_at_most", 2),
    ("chromatic_number_at_most", 3),
    ("diameter_at_most", 1),
    ("diameter_at_most", 2),
]


def test_production_predicates_match_independent_oracle_through_five_vertices():
    for n in range(1, 6):
        for nodes, edges in reference_graphs(n):
            graph = {"nodes": nodes, "edges": edges}
            for predicate in ZERO_ARG_AND_ALIASES:
                got = evaluate_predicate(graph, predicate)
                want = reference_predicate(nodes, edges, predicate)
                assert got == want, (n, edges, predicate, got, want)


def test_parameterized_predicates_match_oracle_through_five_vertices():
    for n in range(1, 6):
        for nodes, edges in reference_graphs(n):
            graph = {"nodes": nodes, "edges": edges}
            for predicate, k in PARAMETERIZED_CASES:
                got = evaluate_atom(graph, predicate, k)
                want = reference_predicate(nodes, edges, predicate, k)
                assert got == want, (n, edges, predicate, k, got, want)
