---
name: graph-counterexample-hunter
description: 将有限简单无向图的自然语言猜想转为结构化任务，调用程序搜索、核验并缩小反例。适用于连通性、二分性、树、欧拉性质、度数、染色数和直径等已支持谓词，以及已有候选图的核验。
---

# graph-counterexample-hunter

将输入解释为全称命题：“对指定范围内的每张图，若满足全部前提，则结论成立”。反例必须是范围内的图，满足全部前提且使结论为假。

## 解析与任务

- 默认有限简单无向图，至少一个顶点。空图、欧拉术语或其他会影响真值的定义有歧义时先澄清。
- 按后端白名单编码谓词；连通性、二分性、树、欧拉性质、度数等仅在后端确实支持时可用。保留合取、否定和析取的原有语义；参数化谓词须提供整数 `k`。例如 `max_degree_at_most(k)`、`min_degree_at_least(k)`、`num_leaves_at_least(k)`、`chromatic_number_at_most(k)`、`diameter_at_most(k)`。命题超出支持表达范围则 `unsupported` 并说明原因。缺少改变真值的条件则澄清。
- 稳定接口为 v0.2.0，字段及入口见 [BACKEND_CONTRACT.md](BACKEND_CONTRACT.md)。示例任务：

```json
{"property_id":"connected_and_bipartite_implies_tree","graph_type":"simple_undirected","premises":["connected","bipartite"],"conclusion":"tree","min_nodes":1,"max_nodes":5,"search_mode":"exhaustive","seed":null}
```

用户指定范围和模式时照用；否则在后端许可下优先穷举 1 至 5 个顶点，并说明默认范围。记录随机搜索实际种子、预算，特殊结构搜索实际覆盖图族。模式不可用时说明原因及实际模式，不能把抽样说成穷举。用户要求弱化条件时展示修改后的完整前提，保留其余条件。

## 后端执行与判断

从本技能目录定位脚本并查阅入口用法；工作目录为技能根目录。将任务和候选图保存为 JSON 文件，按实际路径调用可用 Python，每条命令独立执行。保留退出码、可读输出和错误摘要；不得把用户输入拼接为可执行命令。常见调用形式：

```bash
python scripts/search_engine.py --task examples/connected_and_bipartite_implies_tree.json --minimize
python scripts/verify_candidate.py --task examples/connected_and_bipartite_implies_tree.json --graph examples/mock_skill_candidate.json
python scripts/minimize_counterexample.py --task examples/connected_and_bipartite_implies_tree.json --graph examples/mock_skill_candidate.json
```

用户提供候选图时先核验合法性、范围、每条前提和结论；全部通过才确认反例。候选失败只报告拒绝，除非用户另要求搜索。搜索返回候选后另行调用核验入口，再确认反例。搜索完成后读取模式、覆盖范围、终止原因及结果。脚本异常、超时、不可用或必要证据缺失时为 `inconclusive`。限定预算随机搜索结束且无反例，只能报告该范围/预算内未找到反例。

报告证据应忠实于后端：`graphs_evaluated` 是实际检查数；随机 `max_graphs` 约束生成数 `samples_generated`（重复也计入）；`labeled_graphs_total` 使用相同带标号口径，非同构总数另列。穷举时报告 `premise_satisfying_count`；为零须说明范围内无图满足前提，命题真空成立。抽样计数只针对已检查样本，不足以判断全范围真空。

## 缩小、最小性与证据

仅缩小已核验反例。若有缩小入口，优先减少顶点数，其次边数（除非用户另定准则）；对缩小结果重新核验全部条件。缩小失败或无改进时保留原核验图。报告前后顶点数、边数、是否改进、是否达到单次删点/删边局部最小，以及顶点数/边数最小性各自的证明状态。从小到大穷举首次找到反例仅能证明给定范围内顶点数最小，不能证明边数最小；孤立缩小候选不证明全局最小。只有对同命题及范围覆盖所有更小候选的证据才称“最小反例”，否则称“缩小后的反例”或“原反例”。

有反例时报告顶点、边、每条前提及结论的布尔值和后端结果。使用程序返回的 `evidence.mermaid` 展示图，并用 components、bipartition、cycle、degrees、odd_degree_vertices 等实际证据解释性质；未生成证据的性质只报告核验值，不补造证书。优先读取 `checks.premise_checks` 和 `checks.conclusion_value`，旧布尔字典仅为兼容展示。全范围穷举完成且 `fully_exhausted=true`、无反例时，才可称范围内已证真；否则只报告实际覆盖结果。

## 输出

默认用 Markdown，说明实际完整命题、范围、模式及后端提供的预算/种子/检查数、证据与结论。状态限于：

- `counterexample_found`：后端核验确认反例。
- `verified_true_in_scope`：穷举完成并覆盖范围内所有图，无反例。
- `no_counterexample_in_scope`：随机或 special 搜索按报告范围/预算结束，无经核验反例；这不是证明。
- `unsupported`：图类型或表达超出支持范围。
- `inconclusive`：工具失败、异常终止、证据缺失，或仅核验候选未通过。

只有用户明确要求 Mock 或流程演示时才使用 `mode: mock`，并在开头标注“模拟联调”；否则真实请求为 `mode: live`，仅报告真实后端结果。固定演示命题为“每个连通二分图都是树”，使用任务示例：模拟搜索图为顶点 `[0,1,2,3,4]`、边 `[[0,1],[1,2],[2,3],[3,0],[0,4]]`，模拟核验 `connected=true, bipartite=true, tree=false`；模拟删除顶点 4 及关联边后，四边形仍有相同判定。所有回包都是模拟数据，报告必须标为模拟状态。其他命题可给演示计划，不套用此固定夹具。

若评测要求 JSON，先读取 [references/e2e-report.md](references/e2e-report.md) 并严格遵循其中协议。任务级结构化基准与规则解析器历史回放不能代替真实模型执行；真实执行器说明见 `benchmark/skill_e2e/README.md`。不在主技能中引用基准题数或成绩。

## 组合语法示例

以下是待检查命题：“直径不超过 2，且（不完全或至少有 2 片叶子）的图，一定能二染色”。

```json
{"property_id":"diameter_and_negated_or","graph_type":"simple_undirected","premises":[{"predicate":"diameter_at_most","k":2},{"or":[{"predicate":"complete","negated":true},{"predicate":"num_leaves_at_least","k":2}]}],"conclusion":{"predicate":"chromatic_number_at_most","k":2},"min_nodes":1,"max_nodes":5,"search_mode":"exhaustive","seed":null,"max_graphs":2000}
```

结论可为 `{"predicate":"has_cycle","negated":true}` 或 `{"or":["tree","complete"]}`；整个析取取反写成 `{"or":["tree","complete"],"negated":true}`，不同于只否定一个分支。直径谓词要求连通；单点图直径为 0，满足所有当前允许的正整数阈值。
