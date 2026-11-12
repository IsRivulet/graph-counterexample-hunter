# graph-counterexample-hunter + MathCheck backend / MathCheck-Bench (v0.2.0)

新增真实模型执行与独立评分入口：[benchmark/skill_e2e/README.md](benchmark/skill_e2e/README.md)。本次修改未运行测试或模型评测；目录中的既有结果均是历史快照，不代表修改后的成绩。`skill_live` 仍为历史响应回放。

This package implements the B/C-side backend for the supplied `SKILL.md`: finite simple-undirected graph generation, counterexample search, candidate verification, greedy counterexample reduction, and a reproducible benchmark with independently generated finite-scope labels.

## Scope and semantic contract

- Graph type: finite **simple undirected** graphs only.
- Vertex labels: unique integers; at least one vertex. Empty graphs are intentionally unsupported because the supplied Skill asks the caller to clarify empty-graph semantics.
- A counterexample is a graph in the requested node range that satisfies **every** premise and makes the conclusion predicate false.
- `connected` treats a one-vertex graph as connected.
- `tree` means connected and `|E| = |V| - 1`.
- `eulerian_circuit` means connected and all vertices have even degree.
- `eulerian_trail` means connected and has zero or two odd-degree vertices. Isolated vertices therefore make a graph disconnected when there is more than one vertex.

### Predicate expressions (v0.2)

A premise or the conclusion may be one of three forms:

1. A **bare predicate name** (string), e.g. `"tree"`.
2. A **predicate object** with optional `negated` and `k` fields, e.g.
   `{"predicate": "max_degree_at_most", "k": 2}` or
   `{"predicate": "bipartite", "negated": true}`.
3. A **disjunction (OR) group**, e.g.
   `{"or": [{"predicate": "tree"}, {"predicate": "complete"}]}`. OR groups
   may themselves carry a `negated` flag.

Negation and disjunction let the backend express propositions that were
previously unsupported (e.g. "not a tree", "Eulerian circuit or trail").

### Supported predicates

Zero-argument predicates:

| Predicate | Definition |
|---|---|
| `connected` | The graph is connected. A one-vertex graph is connected. |
| `bipartite` | The graph admits a proper 2-coloring. |
| `tree` | Connected and `|E| = |V| - 1`. |
| `eulerian_circuit` | Connected and every vertex has even degree. |
| `eulerian_trail` | Connected and has zero or two odd-degree vertices. |
| `all_even_degree` | Every vertex has even degree; connectivity is not required. |
| `has_leaf` | At least one vertex has degree one. |
| `has_cycle` | The graph contains an undirected cycle. |
| `complete` | Every pair of distinct vertices is adjacent. |

Parameterized predicates (require an integer `k >= 1`):

| Predicate | Definition |
|---|---|
| `max_degree_at_most(k)` | Every vertex has degree at most `k`. |
| `min_degree_at_least(k)` | Every vertex has degree at least `k`. |
| `num_leaves_at_least(k)` | At least `k` vertices have degree exactly one. |
| `chromatic_number_at_most(k)` | The graph is `k`-colorable. |
| `diameter_at_most(k)` | The graph is connected and every pair of vertices is joined by a path of length at most `k`. |

Legacy aliases `max_degree_at_most_2` and `min_degree_at_least_1` are still
accepted and are equivalent to `max_degree_at_most(2)` and
`min_degree_at_least(1)` respectively.

## Files

```text
mathcheck_backend/
├── mathcheck/
│   ├── graph.py                 # graph validation and graph generators
│   ├── canonical.py             # graph isomorphism canonical form (dedup)
│   ├── predicates.py            # predicate expressions and property checks
│   ├── task.py                   # validates the task format
│   ├── search.py                 # exhaustive / random / special search
│   ├── verify.py                 # independent candidate verification entry
│   ├── minimize.py               # greedy vertex-then-edge reduction
│   └── cli.py                    # JSON command line interface
├── scripts/
│   ├── search_engine.py
│   ├── verify_candidate.py
│   └── minimize_counterexample.py
├── benchmark/
│   ├── tasks.json                # 102 tasks, split by proposition family
│   ├── ground_truth.json         # finite-scope labels and reference witnesses
│   ├── verification_cases.json  # candidate-level positive/negative tests
│   ├── oracle.py                 # separate reference implementation
│   ├── build_benchmark.py        # regenerate benchmark files
│   ├── evaluate.py               # compare search mode to gold labels
│   └── evaluate_verifier.py      # measure verifier precision/recall
└── tests/
```

## Install / requirements

- Python 3.9 or newer.
- Runtime uses only the Python standard library; no `networkx` dependency is required.
- For tests, install `pytest` (development-only): `python -m pip install pytest`.

No package installation is required for a local checkout. Run commands from the project root.

## JSON task format

This is the stable v0.2.0 format used by `SKILL.md`; optional fields include: `max_graphs` (random budget) and `search_mode` values `exhaustive`, `random`, `special`.

```json
{
  "property_id": "connected_and_bipartite_implies_tree",
  "graph_type": "simple_undirected",
  "premises": ["connected", "bipartite"],
  "conclusion": "tree",
  "min_nodes": 1,
  "max_nodes": 5,
  "search_mode": "exhaustive",
  "seed": null,
  "max_graphs": 2000
}
```

`property_id` is descriptive metadata. Actual semantics are determined by `premises` and `conclusion`; do not allow the ID to override them.

Premises and conclusion also accept expression objects (see "Predicate expressions" above). For example:

```json
{
  "premises": [
    {"predicate": "min_degree_at_least", "k": 2},
    {"or": [{"predicate": "has_cycle"}, {"predicate": "complete"}]}
  ],
  "conclusion": {"predicate": "eulerian_circuit", "negated": false},
  "min_nodes": 3,
  "max_nodes": 5,
  "search_mode": "exhaustive"
}
```

## CLI usage

From this directory:

```bash
python scripts/search_engine.py --task examples/connected_and_bipartite_implies_tree.json --minimize
python scripts/verify_candidate.py --task examples/connected_and_bipartite_implies_tree.json --graph examples/mock_skill_candidate.json
python scripts/minimize_counterexample.py --task examples/connected_and_bipartite_implies_tree.json --graph examples/mock_skill_candidate.json
```

Each command writes a JSON result to stdout. Add `--output result.json` to save it to a file. The task and graph inputs must be JSON files; do not interpolate untrusted user text into shell commands.

### Search modes and limits

- `exhaustive`: enumerates every labeled simple undirected graph from `min_nodes` to `max_nodes`. Supported through 6 vertices; larger exhaustive requests return `unsupported` rather than silently sampling.
- `random`: samples `max_graphs` random graphs, deduplicating by graph isomorphism class so duplicate samples are not evaluated again; the budget counts generated samples, including duplicates. If `seed` is omitted, an actual seed is generated and returned. The deterministic density schedule is 0.10, 0.25, 0.50, 0.75, 0.90.
- `special`: searches a documented family set: empty, path, star, balanced complete bipartite, clique-plus-isolate, cycle, complete, cycle-with-leaf, and (when applicable) two disjoint cycles. This is not exhaustive.
- Random and special search are capped at 10 vertices. Random mode uses `max_graphs` (default 2,000).

The backend reports these statuses:

- `counterexample_found`: the candidate graph passed structural, range, all-premise, and conclusion-negation checks.
- `verified_true_in_scope`: an exhaustive search completed and found no counterexample. Because exhaustive search covers every graph in range, this *proves* the proposition holds within the stated vertex range (a stronger claim than "no counterexample found").
- `no_counterexample_in_scope`: a random or special search finished without a witness. The coverage object explicitly records that this is sampled/family-limited evidence, not a proof that no counterexample exists.
- `unsupported`: graph type, predicate, search mode, or requested size exceeds this backend's supported boundary.
- `inconclusive`: malformed task/candidate or another condition prevents a valid conclusion.

## Benchmark

`MathCheck-Bench` contains 102 implication tasks from 34 proposition templates, each repeated at maximum vertex scopes 3, 4, and 5. Splits are by proposition template (not by individual task): 45 train, 27 validation, 30 test. This avoids putting different size variants of the same proposition into different splits.

The labels are generated using the separate `benchmark/oracle.py` reference implementation and exhaustive enumeration of all labeled simple graphs within each task's stated scope. `ground_truth.json` records whether a witness exists and includes a witness when one exists. `verification_cases.json` contains valid witnesses and non-counterexample candidates for candidate-verifier evaluation.

Regenerate the benchmark:

```bash
python benchmark/build_benchmark.py
```

Evaluate the search modes:

```bash
python benchmark/evaluate.py --split test --mode exhaustive
python benchmark/evaluate.py --split test --mode random --budget 2000 --seed 20261105
python benchmark/evaluate.py --split test --mode special
```

Evaluate the candidate verifier:

```bash
python benchmark/evaluate_verifier.py --split all
```

Metrics include counterexample detection rate on gold-positive tasks, false counterexample count, candidate-verification rate, graphs examined, runtime, and per-task records. A random/special miss is not counted as proof of a true proposition.

## Reduction semantics

The reducer repeatedly tries single-vertex deletions first, then single-edge deletions, preserving the counterexample property. It re-verifies the final graph through the candidate verifier. Its strongest claim is `locally_minimal_under_single_vertex_and_edge_deletions`; it does **not** claim a globally minimum counterexample.

## Tests

```bash
python -m pytest -q
```

The predicate implementation is cross-checked against a separately written reference implementation on every labeled simple graph with 1–5 vertices.

## Known limitations / next steps

1. Natural-language parsing is intentionally outside this backend. The Skill layer must map natural language to supported predicate templates and reject ambiguity.
2. Premises are a conjunction of predicate expressions (each possibly an OR group or a negated atom), and the conclusion is a single predicate expression. General quantifiers and nested arbitrary logical formulas are not supported.
3. No directed graphs, multigraphs, empty graphs, weighted graphs, or general logical operators (beyond negation and disjunction) are supported.
4. Exhaustive labeled enumeration becomes expensive quickly; the six-vertex cap is deliberate. Raising it to 7+ vertices requires a native isomorphism-pruning generator (e.g. geng/nauty) rather than the pure-Python canonical form, which is currently used only for random-search deduplication.
5. `special` mode only covers the families listed above; it cannot certify absence of a counterexample.
6. RSI should optimize strategy parameters or a small, versioned search-policy configuration first. It should not modify the predicate definitions, independent verifier, oracle labels, or evaluation criteria.

See `BACKEND_CONTRACT.md` for the exact handoff contract to the Skill orchestrator.

## v0.2.0 evidence and coverage

`graphs_examined` is a compatibility alias of `graphs_evaluated` (actual predicate evaluations). Random `max_graphs` limits `samples_generated`, including `duplicates_skipped`. Exhaustive `graphs_total` / `labeled_graphs_total` count labeled graphs; `isomorphism_classes_total` is separate. `premise_satisfying_count` counts evaluated graphs satisfying all premises. `vacuously_true` is only defined after full exhaustive completion; zero qualifying graphs means vacuous truth in scope.

Verified witnesses include deterministic `evidence`: degrees, components, bipartition when available, an explicit closed cycle when available, odd-degree vertices, leaves, counts and Mermaid. These certificates explain relevant checks; they are not certificates for every supported predicate.

Search `minimality.vertex_minimum_in_scope` is true only for increasing-order exhaustive search. Edge optimality is not claimed. Reduction reports local single-deletion minimality separately; CLI preserves exhaustive vertex minimality when reducing a searched witness. All minimum claims are relative to the task range.

Current real-model evaluation protocol and records: [skill_live/README.md](benchmark/skill_live/README.md). Historical v1 E2E results used a deterministic parser and obsolete capability expectations; they are not current Skill scores.

## Ordered verification checks

`checks.premise_checks` is the authoritative ordered list of `{index, expression, label, value}` records (zero-based index; normalized expression). `checks.conclusion_value` is the explicit truth value of the complete conclusion, including negation/OR. `all_premises_satisfied` and `conclusion_violated` derive from these values. Legacy `premises` and `conclusion` maps remain display-compatible; consumers should use the list to preserve each premise. Shared coverage fields and aliases are constructed centrally by `_coverage`.
