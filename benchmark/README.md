# MathCheck-Bench v0.2.0

真实模型 E2E 执行及分项评分现位于 [skill_e2e/README.md](skill_e2e/README.md)。运行输入与期望答案分离，独立核验返回图，并保留原始 CLI 轨迹。

当前数据集：102题，34个命题模板，各取顶点上限3、4、5；45 train / 27 validation / 30 test，按模板分组。保留 MC001–MC060，新增 MC061–MC102。50题有反例，52题范围内成立，其中6题真空成立。候选核验集152例。

新增模板覆盖全部5个参数化谓词、前提否定、结论否定、前提与结论析取、整体析取否定以及参数/否定/析取组合。`oracle.reference_expr` 直接解释原始表达式，不导入生产归一化或谓词。无反例任务完整穷举，保存满足前提的数量和真空成立标签；有反例任务提供 witness，前提计数仅覆盖已访问部分。

重新生成：`python benchmark/build_benchmark.py`。评测入口保持不变；`reports/` 已更新。参数化谓词还有1–5顶点逐图 oracle 交叉测试。任务状态、逐条前提值、结论值、无反例任务的前提数量与真空成立标签均有回归检查。

这是小规模人工设计的结构化后端基准，不是自然语言 Skill 泛化评测。special 图族与常见命题有重叠；不得从命中率推断一般搜索优势。调参使用 train/validation，test 留作最终报告。

---

# MathCheck-Bench v0.1.0

## Dataset composition

- 60 search tasks from 20 proposition templates.
- Each template is instantiated at `max_nodes = 3, 4, 5`.
- Splits are grouped by proposition template to prevent size variants of the same implication from leaking across splits.
- 30 train / 15 validation / 15 test tasks.
- Independent finite-scope labels: 35 tasks have at least one counterexample; 25 have no counterexample in the specified scope.
- 95 verifier cases: 35 valid counterexamples and 60 non-counterexample candidates.

| Split | Tasks | Tasks with a counterexample in scope |
|---|---:|---:|
| Train | 30 | 17 |
| Validation | 15 | 8 |
| Test | 15 | 10 |
| **Total** | **60** | **35** |

## Ground-truth semantics

A task is positive if there exists at least one labeled simple undirected graph with a vertex count in the task's closed interval that satisfies every premise and violates the conclusion. A task is negative only after the reference implementation has examined every labeled graph in that interval without finding a witness.

Positive tasks include an explicit witness, which is enough to certify existence; the oracle does not need to enumerate the rest of that scope. Negative tasks require complete enumeration. `ground_truth.json` records this distinction using `oracle_scope_exhausted`.

## Intended use

- `train`: explore and tune search policies.
- `validation`: compare candidate strategies and choose policy settings.
- `test`: report final held-out performance. Do not feed test labels or per-task feedback into an RSI loop.

For search evaluation, use `evaluate.py`. For candidate validation, use `evaluate_verifier.py`. The latter checks both valid witnesses and plausible-looking graphs that do not satisfy the counterexample definition.

## Initial smoke-test snapshot

The following deterministic runs were performed against the 15-task test split:

| Method | Counterexample detection | False counterexamples | Mean graphs examined / task |
|---|---:|---:|---:|
| Exhaustive | 10/10 (100%) | 0 | 89.4 |
| Random, budget 50, seed 20261105 | 9/10 (90%) | 0 | 25.7 |
| Special graph families | 10/10 (100%) | 0 | 9.9 |

Verifier smoke test: 95/95 correct (100% accuracy, precision 1.0, recall 1.0).

**Interpretation caution:** this is a small, hand-authored v0.1 benchmark. The special-family test split was constructed from common graph patterns that overlap with the implemented family generator, so its 10/10 result is not evidence that special search is generally superior. The snapshot is a reproducibility check, not a research claim. Increase proposition diversity and add less canonical witnesses before drawing broad conclusions about RSI improvements.
