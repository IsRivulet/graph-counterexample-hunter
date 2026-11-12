# 真实 E2E JSON 报告协议

仅在评测明确要求 JSON 时读取并使用本协议。最终 stdout/message 必须是纯 JSON，不加 Markdown 围栏或前后说明。

顶层对象必须包含以下字段：

```json
{
  "schema_version": "mathcheck.e2e.v1",
  "action": "search",
  "status": "inconclusive",
  "mode": "live",
  "task": null,
  "counterexample": null,
  "coverage": null,
  "checks": null,
  "evidence": null,
  "minimization": null,
  "minimality": null,
  "reason": "非空说明",
  "clarification": null,
  "backend_calls": []
}
```

- `action` 为 `search`、`verify`、`clarify` 或 `unsupported`；`status` 使用主技能定义的五种原状态；`mode` 固定为 `live`。
- `task` 是结构化任务或 null；`counterexample`、`coverage`、`checks`、`evidence`、`minimization`、`minimality` 按后端报告原样填写，未获得时为 null。范围相关字段原样保留，不推算、不改写后端数值。
- `reason` 必须是非空字符串；`clarification` 必须是非空字符串或 null。
- `backend_calls` 按实际调用顺序逐次记录对象：`{"operation":"search|verify|minimize","task_file":"相对路径","graph_file":"相对路径或null","result_file":"相对路径"}`。通过独立 CLI 调用 `scripts/... --output` 将每次结果保存到对应文件；不得人工编写或伪造工具结果。没有调用时为空数组。
- 每次调用使用不同的结果文件；任务和图文件一经调用不得覆盖，可重复引用同一份未修改文件。找到搜索反例后另行调用核验入口；缩小后的图也必须另行调用核验入口，即使缩小器内含核验。只记录真实执行的调用，不补写模拟步骤。
- 搜索反例经 verifier 确认后，必须显式调用 reducer 并保存原始缩小结果；将其返回的 `minimized_graph` 写入单独图文件，再用 verifier 单独复核。即使 reducer 返回 `no_improvement`，也要复核返回图。只有用户明确要求不缩小时才跳过，并在 `reason` 中注明。减小失败或复核失败时保留原始已核验图和对应证据。
- 使用工具的工作目录设置定位技能根目录，每条后端命令只执行一次 `python scripts/入口.py --task 任务.json --output 结果.json`（核验/缩小另加 `--graph 图.json`）。不要把 `cd`、管道、重定向或其他命令与该调用拼接；保留 stdout 中完整 JSON，供执行轨迹与结果文件交叉核对。
- `coverage` 原样取自本次搜索结果（仅候选核验时为 null）。`checks`、`evidence` 对应最终报告中那张图的核验结果；未通过的候选保留核验失败的 `checks`，图与证据为 null。`minimization` 原样取缩小入口结果，或搜索结果中的 `minimization`；`minimality` 对应最终图的证据，不额外合成最小性证明。
- 需要澄清时 `action="clarify"`、`status="inconclusive"`，`task` 可为 null，不调用后端。明确不支持时 `action="unsupported"`、`status="unsupported"`，不调用后端。
- 只有已核验的有效候选图可写入 `counterexample`。若缩小失败或缩小候选核验失败，保留原核验图及其对应证据；不得用未核验/失败的缩小图替换。
- 报告中不可把搜索结果冒充核验结果，也不可把局部最小或限定范围结论扩大为全局最小/真。
