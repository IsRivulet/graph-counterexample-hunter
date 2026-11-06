# 历史模型响应回放

`responses.json` 保存当前 Codex 模型阅读 Skill 后对 13 条自然语言请求给出的任务或澄清决定。`run.py` 只回放这些历史决策并调用后端，不解析或生成模型响应，因此不是实际端到端 Skill 评测。

`expected_outcomes_matched` 只表示动作与历史记录的后端状态相符，不代表自然语言理解正确或任务成功。`semantic_parse_match`、`strict_e2e_pass` 和 `parse_accuracy` 均为 `null`，因为没有独立任务标注，也没有实际运行 Skill。`replay_integrity_pass` 由独立 oracle 对返回反例及缩小结果的复核决定；无效或缺失的缩小图会导致失败并使脚本退出码为 1。

执行：`python benchmark/skill_live/run.py`。

新的正式端到端评测协议见 [`../skill_e2e/README.md`](../skill_e2e/README.md)。历史回放结果应与该协议下的盲测成绩分开报告。
