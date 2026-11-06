# 真实模型 E2E 执行与独立评分

这里提供可运行的执行器和评分器；尚未运行，不附任何成功率。随附10题是公开开发样例，不能当成保留测试集。正式评测请由独立评测者冻结新的输入和答案，按命题家族划分数据，并记录版本。

## 运行

从技能根目录执行。需要 Python 3.9+、已安装并登录的 Codex CLI，以及可用的模型权限。无新增 Python 第三方依赖。命令采用 [OpenAI 官方非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode) 的 `codex exec --json`、`--output-last-message` 和 stdin 输入；CLI 版本及账户能否使用所选模型由本机环境决定。

```powershell
python benchmark/skill_e2e/run.py --model gpt-6-luna --output benchmark/skill_e2e/runs/luna-001
python benchmark/skill_e2e/score.py --run benchmark/skill_e2e/runs/luna-001
```

第一条会真实调用模型并产生费用/额度消耗，每题启动独立新会话，不恢复先前会话。默认每题300秒，可用 `--timeout` 调整；`--ids E001 E005` 仅选择部分题。`--output` 必须是新目录，避免覆盖历史记录。运行阶段不进行评分，也不读取 `expectations.json`。第二条仅读取已保存结果，不再调用模型。

`--codex` 可指定可执行文件路径。Windows npm 的标准 `codex.cmd` 安装会解析成 `node` 加对应 CLI JavaScript 入口；非标准 shim 需要提供原生可执行文件。执行器不使用 `shell=True`，不关闭沙箱或绕过审批。若本机沙箱、登录或 CLI 参数不兼容，原始错误会保存在该题记录中，不能计为通过。

## 输入与隔离边界

- `cases.json` 只包含 `id`、`user_input`，以及可选的 `candidate_graph`、`context`。`context` 表示用户提供的先前上下文，不是自动模拟的多轮会话。
- 答案单独放在 `expectations.json`，格式见随附样例。`task` 的省略字段采用后端默认值。修改用例或答案时创建新版本，不在看完输出后修改答案来提高分数。
- 每题工作区只复制 `SKILL.md`、契约、README、VERSION，以及 `mathcheck/`、`scripts/`、`references/`、`examples/`。不复制 benchmark、答案、历史模型记录或测试目录；运行前后记录运行时文件哈希，模型修改后端不能算通过。
- 这不是操作系统级读取隔离：本机 Codex 配置、全局指令和工作区外可读路径仍可能影响结果。严格盲测应在只挂载运行文件的独立容器/账户执行；本执行器仅保证不主动向模型提供答案。不把本地运行宣称为绝对无污染评测。

每题保留 `input.json`、`prompt.txt`、`events.jsonl`、`stderr.txt`、`final.json` 和完整 `workspace/`；总目录的 `manifest.json` 记录模型请求值、时间、版本、文件哈希、命令、退出码、超时和延迟。模型实际用量从 `turn.completed.usage` 保留；未提供的用量不估造。模型名是请求值，不能代替服务端模型版本证明。超时会尝试终止该 CLI 进程树；保留失败记录，不自动重试挑选最好结果。

## 评分

最终消息须遵循 [报告协议](../../references/e2e-report.md)。真实 CLI 调用必须使用 `--output` 保存后端结果；结果文件逐次独立，任务与图文件可以复用但不可覆盖。CLI 同时把相同 JSON 输出到 stdout。评分核对成功的 Codex `command_execution` 事件、成对命令参数、实际输入、stdout 和结果文件，而非相信模型自报“已经验证”。只接受单条 Python CLI 命令及常规 shell 包装，不接受复合命令、重定向或注释作为执行证据；遇不识别的事件/命令格式保守判失败并保留原文。此版本只支持这种 Codex JSONL 事件格式。

分项检查执行、动作、状态、任务语义、工具证据、范围、反例、显式复核、缩小和最小性：

- 前提合取与结论分别按布尔逻辑等价比较，支持排列、别名和 De Morgan 变形。范围、模式、种子、预算单独比较。只比较逻辑等价，不穷尽图论定理等价；如将二染色改写为二分图，应在冻结答案时统一编码。
- 返回图由独立 oracle 校验结构、范围和反例性质，不要求与参考图完全相同。无效图不计成功。
- 搜索反例和缩小后反例必须有显式核验调用；范围内证真必须绑定完整穷举覆盖。缩小必须保留有效性且不能变大；局部最小声明另外逐项删除重算。
- 缺失/损坏记录、退出失败、超时、变更后端、任务错译和不一致声明均阻止自动通过。题目失败仍进入总分母。
- 原始 trace 与文件的一致性检查不是防篡改审计。自然语言解释是否准确、澄清是否必要、是否偷换用户命题，需要人工复核；不能仅凭出现关键词判为正确。

随附样例要求人工复核，所以首次评分的 `strict_pass` 可能为 `null`，表示等待评审，不计为通过。阅读每题原始请求、工具记录与最终报告后，另建例如 `review.json`：

```json
{
  "E001": {"approved": true, "notes": "已核对命题、证据和范围限定，无全局最小性误报。"},
  "E009": {"approved": true, "notes": "澄清问题覆盖了用户未确定的欧拉术语约定。"}
}
```

```powershell
python benchmark/skill_e2e/score.py --run benchmark/skill_e2e/runs/luna-001 --manual-review review.json
```

`scores.json` 同时报 `automatic_pass_count`、严格通过数、待人工复核数、各分项分子/分母及反例 precision/recall。只有自动检查通过且需要的人工复核批准后，才能记严格通过。返回码0表示所选题全部严格通过；返回码1包含失败或待复核，不应抹掉待复核状态。

当前未实现澄清后自动续聊和故障注入。后续可扩充这些流程；历史 `skill_live` 仍只是决定回放，旧 E2E harness 仍只是规则解析器基线。
