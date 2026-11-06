# MathCheck-E2E-Bench v1.0.0

## 1. 这份测试集测什么

本测试集专门评估 MathCheck Skill 的端到端表现，而不是单独评估图枚举算法。测试链路为：

`自然语言输入 → 命题解析 → 结构化任务 → 搜索/候选核验 → 反例缩小 → 缩小后复核 → 最终报告`

此前的 `MathCheck-Bench` 60 个任务主要评价后端搜索和验证能力；本套 `MathCheck-E2E-Bench` 关注 Skill 是否正确理解用户输入、保持逻辑方向和前提、选择正确入口，并如实表达证据边界。两套测试应并行使用。

## 2. 文件说明

- `MathCheck_E2E_Bench_v1.json`：正式数据集。每条记录包含自然语言输入、预期动作、预期结构化任务、期望状态、参考反例/候选图和必须满足的报告断言。
- `MathCheck_E2E_Case_Index.csv`：便于筛选和分工的用例索引。
- `README.md`：测试协议、指标和使用说明。

## 3. 当前测试覆盖

共 **42 条**端到端用例，分为四大类：

| 类别 | 覆盖重点 |
|---|---|
| 命题解析、搜索与报告 | 单前提/多前提、欧拉性质、连通/二分/树/度数、正反方向 |
| 范围和搜索模式 | 默认范围、有限范围变化、穷举、随机、特殊结构搜索及覆盖声明 |
| 澄清与能力边界 | 空图约定、欧拉术语歧义、方向缺失、有向图、多重图、否定、析取、后端规模上限 |
| 候选核验与缩小 | 合法反例、违反前提、结论为真、结构非法、范围外候选、缩小及复核 |
| 后端故障处理 | 搜索器不可用、核验器异常、缩小阶段失败后的安全回退（需测试桩注入） |

## 4. 数据结构与执行方式

每条 case 的关键字段：

- `user_input`：原样发送给 Skill 的用户输入。
- `expected.action`：预期 Skill 分支，如 `parse_search`、`verify_candidate`、`clarify_before_search`。
- `expected.normalized_task`：预期任务。比较时忽略 `property_id` 命名差异，但不能忽略前提、结论、范围、模式、seed 和预算。
- `expected.status`：预期终态。对澄清用例，`inconclusive` 表示当前信息不足，应先澄清，而不是直接调用后端。
- `expected.reference_witness`：参考反例。它是可接受证据样例，不要求系统输出完全相同的边集。
- `expected.must_assert`：输出必须体现的关键断言。
- `expected.must_not_claim`：禁止出现的过度结论。
- `fixtures.candidate_graph`：候选图核验/缩小用例要注入的输入图。
- `expected.oracle_validation`：独立参考程序的真值检查摘要。

推荐执行：逐条开启新 Skill 会话，提交 `user_input`；存在 `fixtures.candidate_graph` 时，将图作为用户提供的候选图一并传入。保存 Skill 最终报告及工具调用日志，然后按断言评分。

## 5. 评分指标建议

建议将总分拆成以下维度，而不是只看“是否找到反例”：

1. **解析正确率（20%）**：前提、结论、方向、图类型、顶点范围和搜索模式是否解析正确。
2. **端到端结论正确率（20%）**：反例是否真实有效；无反例时是否与范围内真值一致；unsupported/clarification 是否分流正确。
3. **核验可靠性（15%）**：候选图的结构、顶点范围、每条前提、结论为假是否全部独立检查。重点记录 false positive。
4. **覆盖与证据诚实性（15%）**：是否区分 exhaustive、random、special；是否报告 seed、budget、graphs_examined、fully_exhausted 和终止原因；是否避免把有限/抽样结果说成证明。
5. **反例质量与缩小（10%）**：反例是否易读；是否优先减少顶点再减少边；缩小后是否复核；是否准确表述局部最小而非全局最小。
6. **效率（10%）**：LLM tokens、后端调用次数、枚举图数和墙钟时间。
7. **报告质量（10%）**：是否给出任务、证据、检查结果、范围和恰当结论。

上述权重是建议初始配置，团队可按课程项目重点调整。若某条用例不涉及缩小，相关项应标为 N/A 并按剩余维度归一化，不要把未要求的功能当作失败。

### 必须单独报告的指标

- **Counterexample precision** = 经独立核验有效的系统反例数 / 系统声称找到的反例数。
- **Counterexample recall** = 找到有效反例的 gold-positive 用例数 / 全部 gold-positive 用例数。
- **False-positive rate**：把不满足全部前提、结论未被违反或图结构非法的候选误报为反例的比例。
- **Task parse exact-match**：结构化任务核心语义字段完全正确的比例。
- **Scope honesty rate**：正确区分穷举、抽样和特殊图族覆盖的比例。
- **Clarification/unsupported accuracy**：对歧义和能力边界是否正确停止调用并解释。
- **Efficiency**：平均/中位 token、延迟、后端调用数、graphs_examined。
- **Witness quality**：反例顶点数、边数、缩小前后变化及可读性。

## 6. 关键评测原则

- **不要要求精确匹配某一张反例图。** 多张图可能都满足反例定义；按谓词和结构条件验证即可。
- **不要把 `no_counterexample_in_scope` 当作命题已被证明。** 特别是 random 和 special 模式，只能报告指定采样预算或图族内未命中。
- **无反例用例必须检查 `fully_exhausted`。** 对 exhaustive 用例，只有完整覆盖请求范围时才可判定该范围内未发现反例。
- **候选核验失败不是搜索成功。** 候选图不满足前提、结论为真或结构非法，均应拒绝；若用户未要求继续搜索，不应自行声称已完成搜索。
- **缩小必须复核。** 缩小后的图只有再次通过 verifier 才可报告；`minimality_claim` 仅可使用后端实际支持的局部单点删除语义。
- **记录资源成本。** 同一用例比较 Skill 改版前后时，固定模型、运行环境和后端版本，记录 tokens、工具调用数、运行时间和搜索覆盖。

## 7. 与原 60-task 后端 Benchmark 的关系

推荐采用两层评测：

- **Backend benchmark（已有 60 tasks）**：检验枚举搜索、随机/特殊模式、独立 oracle、一致性和 verifier 的算法层能力。
- **E2E benchmark（本文件 39 cases）**：检验自然语言理解、任务构建、工具编排、边界处理、反例缩小与最终报告。

如果后端 benchmark 分数高而 E2E 分数低，问题更可能出在 Skill 解析/编排/报告；如果两层都低，再排查谓词实现、搜索策略和候选核验。
