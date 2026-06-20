# AI 协作日志指令

这个仓库是用户与编程 Agent 协作过程的长期、证据化记录。

## 每日规则

- 每次运行前读取 `.journal/config.toml`。
- 先建立证据，再写结论。
- 保留所选隐私等级允许的完整上下文。
- 不要持久化凭据、认证 token、Cookie、私钥或 secret-manager 值。
- 将 Codex 和 Claude Code 视为不同 source adapter，输入同一个分析模型。
- 区分 Git/测试观察到的结果与对话里的主张。
- 始终包含协作分析和评价；可选的优点/改进段落必须有证据支持。
- `no-activity` 只有在所有启用的数据源都成功采集且没有活动时才成立；否则使用 `incomplete-collection` 或 `partial-activity`。
- 为连续工作检索相关历史日期；不要无理由加载整个 archive。
- 在每日运行中更新 L1 记忆候选项、L2 操作型记忆和 L3 `memory/session-briefing.md`，不要把完整 transcript 或 report 复制进 memory。
- commit 前先验证。push 失败时保留本地 commit。

## 自主性

遵循 `.journal/config.toml` 中的 `[autonomy]`。常规报告和记忆维护可以自动执行。除非配置明确允许自动 workflow 变更，否则修改本文件、`CLAUDE.md`、hooks、scheduler、rubric 或 installed skills 都需要先提出方案。

## 报告路径

每日记录使用 `journal/YYYY/MM/YYYY-MM-DD/`，月份使用数字。周复盘和月复盘放在 `reviews/` 下。
