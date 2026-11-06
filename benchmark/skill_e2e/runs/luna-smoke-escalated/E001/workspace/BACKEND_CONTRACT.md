# MathCheck backend contract for Skill integration

This document specifies the stable v0.2.0 task and result contract used by `SKILL.md`.

## Entry points

| Responsibility | Script | Input |
|---|---|---|
| Search engine (B) | `scripts/search_engine.py` | `--task task.json` |
| Candidate verifier (B) | `scripts/verify_candidate.py` | `--task task.json --graph graph.json` |
| Reducer (C) | `scripts/minimize_counterexample.py` | `--task task.json --graph graph.json` |

All commands return a JSON object on stdout. `--output path.json` saves the same result to disk. The Python APIs are `mathcheck.search.search_task`, `mathcheck.verify.verify_candidate`, and `mathcheck.minimize.minimize_counterexample`.

`--output` also preserves the same JSON on stdout, allowing the E2E scorer to cross-check the saved result against the actual CLI trace. For model final reports and per-call artifact records, see [references/e2e-report.md](references/e2e-report.md); for fresh model execution, see [benchmark/skill_e2e/README.md](benchmark/skill_e2e/README.md). Historical response replay is not a live E2E run.

## Task fields

Required: `premises` (array of predicate expressions), `conclusion` (one predicate expression). A predicate expression is a bare predicate-name string, a predicate object `{"predicate": ..., "negated": bool, "k": int}`, or an OR group `{"or": [...], "negated": bool}`. Defaults: `graph_type=simple_undirected`, `min_nodes=1`, `max_nodes=5`, `search_mode=exhaustive`, `seed=null`, `max_graphs=2000`.

The supplied `property_id` is preserved as metadata only. Search semantics are derived from the actual `premises` and `conclusion`, never from the ID.

## Predicate whitelist

Zero-argument: `connected`, `bipartite`, `tree`, `eulerian_circuit`, `eulerian_trail`, `all_even_degree`, `has_leaf`, `has_cycle`, `complete`.

Parameterized (require `k >= 1`): `max_degree_at_most(k)`, `min_degree_at_least(k)`, `num_leaves_at_least(k)`, `chromatic_number_at_most(k)`, `diameter_at_most(k)`.

Legacy aliases `max_degree_at_most_2` and `min_degree_at_least_1` are accepted and mapped to `max_degree_at_most(2)` and `min_degree_at_least(1)`.

Any predicate expression may carry a `negated` flag, and any premise may be an OR group. The definitions (especially Eulerian properties and the one-vertex graph convention) are in `README.md` and `mathcheck/predicates.py`. If the user's intended convention differs, the Skill should clarify before invoking the backend.

## Search result shape

```json
{
  "status": "counterexample_found",
  "mode": "live",
  "task": {"...": "normalized task"},
  "coverage": {
    "search_mode": "exhaustive",
    "min_nodes": 1,
    "max_nodes": 5,
    "graphs_examined": 17,
    "graphs_total": 1099,
    "fully_exhausted": false,
    "termination_reason": "counterexample_found"
  },
  "counterexample": {"nodes": [0, 1, 2], "edges": [[0, 1], [0, 2], [1, 2]]},
  "checks": {
    "premises": {"connected": true},
    "conclusion": {"tree": false},
    "is_counterexample": true
  },
  "minimization": null,
  "reason": "..."
}
```

Exact coverage fields differ by search mode. Do not infer omitted coverage or claim full exhaustion unless `fully_exhausted` is true. In exhaustive mode, `graphs_examined` and `graphs_evaluated` count labeled graphs visited; `graphs_total` and `labeled_graphs_total` count all labeled graphs in scope. `isomorphism_classes_total` separately counts non-isomorphic classes. Random mode adds `isomorphic_duplicates_skipped`.

## Status mapping to uploaded SKILL.md

- `counterexample_found`: candidate verified.
- `verified_true_in_scope`: exhaustive search completed with no counterexample; the proposition holds within the stated vertex range.
- `no_counterexample_in_scope`: a random/special search finished without a found witness. Read `coverage.search_mode` and `coverage.fully_exhausted` before describing what was covered.
- `unsupported`: explicit unsupported type/predicate/mode/size.
- `inconclusive`: invalid task, invalid graph, candidate does not meet the counterexample definition, or no reliable result.

## Candidate verification

The verifier checks, in order: graph structure (no loops, no duplicate edges, endpoints exist), vertex count range, each premise, and conclusion falsity. Only if all pass does it return `counterexample_found`.

## Reduction

The reducer accepts only an already verified counterexample. It tries vertex deletion before edge deletion, repeatedly, and re-verifies the final graph. `minimization.minimality_claim` is local single-deletion minimality, not global minimum size.

## Benchmark integration

`benchmark/tasks.json` includes extra `task_id` and `split` fields. Remove these metadata fields before invoking the backend, or pass the full object (the parser ignores them). Gold labels are in `benchmark/ground_truth.json`; the independent candidate-verification set is in `benchmark/verification_cases.json`.

## v0.2.0 evidence and coverage

`graphs_examined` is a compatibility alias of `graphs_evaluated` (actual predicate evaluations). Random `max_graphs` limits `samples_generated`, including `duplicates_skipped`. Exhaustive `graphs_total` / `labeled_graphs_total` count labeled graphs; `isomorphism_classes_total` is separate. `premise_satisfying_count` counts evaluated graphs satisfying all premises. `vacuously_true` is only defined after full exhaustive completion; zero qualifying graphs means vacuous truth in scope.

Verified witnesses include deterministic `evidence`: degrees, components, bipartition when available, an explicit closed cycle when available, odd-degree vertices, leaves, counts and Mermaid. These certificates explain relevant checks; they are not certificates for every supported predicate.

Search `minimality.vertex_minimum_in_scope` is true only for increasing-order exhaustive search. Edge optimality is not claimed. Reduction reports local single-deletion minimality separately; CLI preserves exhaustive vertex minimality when reducing a searched witness. All minimum claims are relative to the task range.

Current real-model evaluation protocol and records: [skill_live/README.md](benchmark/skill_live/README.md). Historical v1 E2E results used a deterministic parser and obsolete capability expectations; they are not current Skill scores.

## Ordered verification checks

`checks.premise_checks` is the authoritative ordered list of `{index, expression, label, value}` records (zero-based index; normalized expression). `checks.conclusion_value` is the explicit truth value of the complete conclusion, including negation/OR. `all_premises_satisfied` and `conclusion_violated` derive from these values. Legacy `premises` and `conclusion` maps remain display-compatible; consumers should use the list to preserve each premise. Shared coverage fields and aliases are constructed centrally by `_coverage`.
