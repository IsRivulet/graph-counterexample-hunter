"""Build the fixed MathCheck-Bench v0.2 dataset and independent gold labels."""

import json
from pathlib import Path

from oracle import reference_counterexample, reference_graphs

ROOT = Path(__file__).resolve().parent

# Each template is a finite implication: conjunction(premises) => conclusion.
# All predicates follow the definitions documented in README.md.
TEMPLATES = [
    ("connected_implies_bipartite", ["connected"], "bipartite", "train"),
    ("connected_implies_tree", ["connected"], "tree", "train"),
    ("tree_implies_connected", ["tree"], "connected", "train"),
    ("tree_implies_bipartite", ["tree"], "bipartite", "train"),
    ("tree_implies_eulerian_trail", ["tree"], "eulerian_trail", "train"),
    ("eulerian_circuit_implies_all_even", ["eulerian_circuit"], "all_even_degree", "train"),
    ("eulerian_circuit_implies_tree", ["eulerian_circuit"], "tree", "train"),
    ("eulerian_trail_implies_connected", ["eulerian_trail"], "connected", "train"),
    ("all_even_implies_eulerian_circuit", ["all_even_degree"], "eulerian_circuit", "train"),
    ("bipartite_implies_connected", ["bipartite"], "connected", "train"),
    ("bipartite_implies_tree", ["bipartite"], "tree", "validation"),
    ("complete_implies_connected", ["complete"], "connected", "validation"),
    ("complete_implies_eulerian_circuit", ["complete"], "eulerian_circuit", "validation"),
    ("has_cycle_implies_connected", ["has_cycle"], "connected", "validation"),
    ("connected_even_implies_eulerian_circuit", ["connected", "all_even_degree"], "eulerian_circuit", "validation"),
    ("connected_bipartite_tree_implies_eulerian_trail", ["connected", "bipartite", "tree"], "eulerian_trail", "test"),
    ("connected_maxdeg2_implies_eulerian_trail", ["connected", "max_degree_at_most_2"], "eulerian_trail", "test"),
    ("connected_maxdeg2_implies_tree", ["connected", "max_degree_at_most_2"], "tree", "test"),
    ("tree_with_leaf_implies_has_cycle", ["tree", "has_leaf"], "has_cycle", "test"),
    ("connected_cyclic_implies_eulerian", ["connected", "has_cycle"], "eulerian_circuit", "test"),
]


# Extension templates are split by proposition family, preserving MC001–MC060.
def atom(name, k=None, negated=False):
    result = {"predicate": name}
    if k is not None:
        result["k"] = k
    if negated:
        result["negated"] = True
    return result


TEMPLATES += [
    ("degree2_implies_leaf", [atom("min_degree_at_least", 2)], "has_leaf", "train"),
    ("maxdegree1_implies_bipartite", [atom("max_degree_at_most", 1)], "bipartite", "train"),
    ("two_leaves_implies_tree", [atom("num_leaves_at_least", 2)], "tree", "train"),
    ("two_color_implies_bipartite", [atom("chromatic_number_at_most", 2)], "bipartite", "train"),
    ("diameter2_implies_complete", [atom("diameter_at_most", 2)], "complete", "train"),
    ("not_bipartite_implies_cycle", [atom("bipartite", negated=True)], "has_cycle", "validation"),
    ("tree_implies_not_cycle", ["tree"], atom("has_cycle", negated=True), "validation"),
    ("cycle_or_complete_implies_connected", [{"or": ["has_cycle", "complete"]}], "connected", "validation"),
    ("impossible_degree5_implies_tree", [atom("min_degree_at_least", 5)], "tree", "validation"),
    ("contradictory_tree_implies_complete", ["tree", atom("tree", negated=True)], "complete", "test"),
    ("negated_or_implies_connected", [{"or": ["tree", atom("chromatic_number_at_most", 2)], "negated": True}], "connected", "test"),
    ("diameter_and_negated_or", [atom("diameter_at_most", 2), {"or": [atom("complete", negated=True), atom("num_leaves_at_least", 2)]}], atom("chromatic_number_at_most", 2), "test"),
    ("tree_implies_cycle_or_two_color", ["tree"], {"or": ["has_cycle", atom("chromatic_number_at_most", 2)]}, "test"),
    ("diameter1_implies_complete", [atom("diameter_at_most", 1)], "complete", "test"),
]


def main():
    tasks = []
    ground_truth = []
    verification_cases = []
    task_index = 0

    for template_id, premises, conclusion, split in TEMPLATES:
        for max_nodes in (3, 4, 5):
            task_index += 1
            task_id = "MC{0:03d}".format(task_index)
            task = {
                "task_id": task_id,
                "split": split,
                "property_id": template_id,
                "graph_type": "simple_undirected",
                "premises": premises,
                "conclusion": conclusion,
                "min_nodes": 1,
                "max_nodes": max_nodes,
                "search_mode": "exhaustive",
                "seed": None,
                "max_graphs": 2000,
            }
            tasks.append(task)

            found = None
            non_counterexample = None
            graphs_checked = 0
            premise_satisfying_count = 0
            total_graphs = sum(1 << (n * (n - 1) // 2) for n in range(1, max_nodes + 1))
            for n in range(1, max_nodes + 1):
                for nodes, edges in reference_graphs(n):
                    graphs_checked += 1
                    is_ce, premise_values, conclusion_value = reference_counterexample(nodes, edges, premises, conclusion)
                    premise_satisfying_count += int(all(premise_values.values()))
                    record = {
                        "nodes": nodes,
                        "edges": edges,
                        "premise_values": premise_values,
                        "conclusion_value": conclusion_value,
                    }
                    if is_ce and found is None:
                        found = record
                    if not is_ce and non_counterexample is None:
                        non_counterexample = record
                    if found is not None and non_counterexample is not None:
                        break
                if found is not None and non_counterexample is not None:
                    break

            # For gold labels, complete the entire finite scope if there was no witness.
            if found is None:
                graphs_checked = total_graphs
            expected = "counterexample_exists_in_scope" if found is not None else "no_counterexample_in_scope"
            ground_truth.append({
                "task_id": task_id,
                "property_id": template_id,
                "split": split,
                "expected_status": expected,
                "counterexample": found,
                "graphs_in_scope": total_graphs,
                "oracle_graphs_checked": graphs_checked,
                "oracle_label_certified": True,
                "oracle_scope_exhausted": found is None,
                "premise_satisfying_count": premise_satisfying_count,
                "vacuously_true": premise_satisfying_count == 0 if found is None else False,
                "expected_backend_status": "counterexample_found" if found is not None else "verified_true_in_scope",
                "oracle_method": ("independent reference implementation; a verified witness certifies existence" if found is not None else "independent reference implementation + exhaustive enumeration certifies no witness in scope"),
            })

            if found is not None:
                verification_cases.append({
                    "case_id": task_id + "_VALID_CE",
                    "task_id": task_id,
                    "kind": "valid_counterexample",
                    "graph": {"nodes": found["nodes"], "edges": found["edges"]},
                    "expected_is_counterexample": True,
                    "expected_premise_values": found["premise_values"],
                    "expected_conclusion_value": found["conclusion_value"],
                })
            if non_counterexample is not None:
                verification_cases.append({
                    "case_id": task_id + "_NON_CE",
                    "task_id": task_id,
                    "kind": "not_a_counterexample",
                    "graph": {"nodes": non_counterexample["nodes"], "edges": non_counterexample["edges"]},
                    "expected_is_counterexample": False,
                    "expected_premise_values": non_counterexample["premise_values"],
                    "expected_conclusion_value": non_counterexample["conclusion_value"],
                })

    dataset = {
        "benchmark": "MathCheck-Bench",
        "version": "0.2.0",
        "description": "Finite-scope counterexample-search tasks over simple undirected graphs.",
        "graph_type": "simple_undirected",
        "vertex_scopes": [3, 4, 5],
        "task_count": len(tasks),
        "split_counts": {
            split: sum(1 for t in tasks if t["split"] == split)
            for split in ("train", "validation", "test")
        },
        "tasks": tasks,
    }
    gold = {
        "benchmark": "MathCheck-Bench",
        "version": "0.2.0",
        "label_semantics": "counterexample_exists_in_scope means at least one graph in the finite specified scope satisfies every premise and violates the conclusion.",
        "ground_truth_is_independent_of_production_backend": True,
        "cases": ground_truth,
    }
    verification = {
        "benchmark": "MathCheck-Bench-Verifier",
        "version": "0.2.0",
        "case_count": len(verification_cases),
        "cases": verification_cases,
    }

    (ROOT / "tasks.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "ground_truth.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "verification_cases.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote {0} tasks, {1} verification cases.".format(len(tasks), len(verification_cases)))
    print("Split counts: {0}".format(dataset["split_counts"]))
    print("Ground-truth positives: {0}".format(sum(1 for x in ground_truth if x["counterexample"] is not None)))


if __name__ == "__main__":
    main()
