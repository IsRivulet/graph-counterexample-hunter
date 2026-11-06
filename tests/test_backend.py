import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mathcheck.search import search_task
from mathcheck.verify import verify_candidate
from mathcheck.minimize import minimize_counterexample


def sample_task():
    return {
        "property_id": "connected_and_bipartite_implies_tree",
        "graph_type": "simple_undirected",
        "premises": ["connected", "bipartite"],
        "conclusion": "tree",
        "min_nodes": 1,
        "max_nodes": 5,
        "search_mode": "exhaustive",
        "seed": None,
    }


def test_skill_mock_fixture_is_verified_and_minimized_to_four_cycle():
    task = sample_task()
    graph = {
        "nodes": [0, 1, 2, 3, 4],
        "edges": [[0, 1], [1, 2], [2, 3], [3, 0], [0, 4]],
    }
    checked = verify_candidate(task, graph)
    assert checked["status"] == "counterexample_found"
    reduced = minimize_counterexample(task, graph)
    assert reduced["verification"]["status"] == "counterexample_found"
    assert reduced["minimized_size"] == {"nodes": 4, "edges": 4}


def test_exhaustive_search_finds_verified_counterexample():
    result = search_task(sample_task())
    assert result["status"] == "counterexample_found"
    assert result["checks"]["is_counterexample"] is True


def test_exhaustive_no_counterexample_is_fully_exhausted_and_verified_true():
    task = {
        "premises": ["tree"], "conclusion": "connected", "min_nodes": 1,
        "max_nodes": 5, "search_mode": "exhaustive",
    }
    result = search_task(task)
    assert result["status"] == "verified_true_in_scope"
    assert result["coverage"]["fully_exhausted"] is True


def test_parameterized_predicate_min_degree():
    task = {
        "premises": [{"predicate": "min_degree_at_least", "k": 2}],
        "conclusion": "has_leaf", "min_nodes": 1, "max_nodes": 5,
        "search_mode": "exhaustive",
    }
    result = search_task(task)
    # A 2-regular cycle (e.g. C3) has min_degree 2 and no leaf -> counterexample.
    assert result["status"] == "counterexample_found"


def test_negated_conclusion():
    task = {
        "premises": ["connected"],
        "conclusion": {"predicate": "bipartite", "negated": True},
        "min_nodes": 1, "max_nodes": 5, "search_mode": "exhaustive",
    }
    result = search_task(task)
    # A connected bipartite graph (e.g. a single vertex) makes "not bipartite" false.
    assert result["status"] == "counterexample_found"


def test_disjunctive_premise():
    task = {
        "premises": [{"or": [{"predicate": "has_cycle"}, {"predicate": "complete"}]}],
        "conclusion": "connected", "min_nodes": 1, "max_nodes": 5,
        "search_mode": "exhaustive",
    }
    result = search_task(task)
    # A graph with a cycle that is disconnected (e.g. C3 + isolate) violates "connected".
    assert result["status"] == "counterexample_found"


def test_legacy_alias_still_works():
    task = {
        "premises": ["max_degree_at_most_2"], "conclusion": "tree",
        "min_nodes": 1, "max_nodes": 5, "search_mode": "exhaustive",
    }
    result = search_task(task)
    # max_degree<=2 forbids leaves of degree 1? No: C3 has all degree 2, not a tree.
    assert result["status"] == "counterexample_found"


def test_random_search_reports_isomorphic_dedup():
    task = {
        "premises": ["connected"], "conclusion": "tree",
        "min_nodes": 1, "max_nodes": 4, "search_mode": "random",
        "max_graphs": 200, "seed": 123,
    }
    result = search_task(task)
    assert "isomorphic_duplicates_skipped" in result["coverage"]



def test_random_seed_is_reproducible():
    task = sample_task()
    task.update({"search_mode": "random", "max_graphs": 200, "seed": 123})
    a = search_task(task)
    b = search_task(task)
    assert a["counterexample"] == b["counterexample"]
    assert a["coverage"]["graphs_examined"] == b["coverage"]["graphs_examined"]


def test_unsupported_predicate_is_not_silently_accepted():
    task = {"premises": ["planar"], "conclusion": "tree", "search_mode": "exhaustive"}
    result = search_task(task)
    assert result["status"] == "unsupported"


def test_malformed_candidate_is_rejected():
    task = sample_task()
    graph = {"nodes": [0, 1], "edges": [[0, 0]]}
    result = verify_candidate(task, graph)
    assert result["status"] == "inconclusive"
    assert result["checks"]["graph_structure_valid"] is False


def test_coverage_uses_comparable_counts_and_vacuity():
    result = search_task({"premises": [{"predicate": "min_degree_at_least", "k": 3}],
                          "conclusion": "tree", "max_nodes": 3})
    c = result["coverage"]
    assert c["graphs_evaluated"] == c["labeled_graphs_total"] == 11
    assert c["isomorphism_classes_total"] == 7
    assert c["premise_satisfying_count"] == 0
    assert c["vacuously_true"] is True
    result = search_task({"premises": ["tree"], "conclusion": "connected", "max_nodes": 3})
    assert result["coverage"]["premise_satisfying_count"] > 0
    assert result["coverage"]["vacuously_true"] is False


def test_random_budget_conservation():
    result = search_task({"premises": ["tree"], "conclusion": "connected",
                          "max_nodes": 2, "search_mode": "random", "max_graphs": 40, "seed": 4})
    c = result["coverage"]
    assert c["samples_generated"] == c["graphs_evaluated"] + c["duplicates_skipped"] == 40
    assert c["graphs_evaluated"] == sum(c["size_counts_examined"].values())
    assert c["vacuously_true"] is None


def test_cycle_and_bipartition_certificates_are_checkable():
    result = search_task(sample_task())
    graph, evidence = result["counterexample"], result["evidence"]
    edges = {frozenset(e) for e in graph["edges"]}
    cycle = evidence["cycle"]
    assert cycle[0] == cycle[-1]
    assert len(set(cycle[:-1])) == len(cycle) - 1 >= 3
    assert all(frozenset([u, v]) in edges for u, v in zip(cycle, cycle[1:]))
    left, right = map(set, evidence["bipartition"])
    assert not left & right and left | right == set(graph["nodes"])
    assert all((u in left) != (v in left) for u, v in graph["edges"])
    assert result["minimality"]["vertex_minimum_in_scope"] is True
    assert result["minimality"]["edge_minimum_at_minimum_vertices"] is False
    reduced = minimize_counterexample(sample_task(), graph)
    assert reduced["minimality"]["local_single_deletion_minimum"] is True
    assert reduced["minimality"]["vertex_minimum_in_scope"] is False


def test_ordered_checks_preserve_duplicate_expressions_at_evaluation_boundary():
    from mathcheck.predicates import normalize_conditions, evaluate_task_conditions
    premises, conclusion = normalize_conditions(["tree", "tree"], "connected")
    result = evaluate_task_conditions({"nodes": [0], "edges": []}, premises, conclusion)
    assert [item["index"] for item in result["premise_checks"]] == [0, 1]
    assert [item["value"] for item in result["premise_checks"]] == [True, True]
    assert result["conclusion_value"] is True
    assert result["all_premises_satisfied"] is True
