# MathCheck E2E formal set, runnable conversion

This folder contains runner-compatible versions of the project's 42-case `MathCheck_E2E_Bench_v1.json` specification.

- `cases.json`: 39 live inputs, with any candidate graph fixtures included as user input.
- `expectations.json`: matching frozen labels in the format consumed by `score.py`.
- `exclusions.json`: the three backend fault-injection cases that the live runner cannot simulate.
- `prepare_formal_cases.py`: deterministic converter from the source specification.

The converter retains the source case IDs and user text. It does not place answer labels in `cases.json`. Each converted expectation requires manual review because the written interpretation, evidence quality, and ambiguity handling need human judgment.

For exhaustive cases labeled `no_counterexample_in_scope` in the source specification, the converter expects `verified_true_in_scope`, matching the Skill's distinction between completed exhaustive search and a bounded random/special-search miss. The two random/special cases retain `no_counterexample_in_scope`.

Run from the `mathcheck_backend` directory. For a Skill/baseline comparison, use the same input file and model for both commands, changing only `--condition` and the new output directory. Use `--ids` with identical IDs for a pilot or stratified subset.

```powershell
python benchmark/skill_e2e/run.py --cases benchmark/skill_e2e/formal_v1/cases.json --condition skill --model gpt-6-luna --output benchmark/skill_e2e/runs/formal-skill
python benchmark/skill_e2e/run.py --cases benchmark/skill_e2e/formal_v1/cases.json --condition baseline --model gpt-6-luna --output benchmark/skill_e2e/runs/formal-baseline
```

Score each run separately with `--expectations benchmark/skill_e2e/formal_v1/expectations.json` and review both outputs blind to condition before comparing.
