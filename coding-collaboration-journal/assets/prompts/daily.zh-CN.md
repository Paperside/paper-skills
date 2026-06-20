# 每日自动化提示

以 **daily** 模式运行这个已安装的 journal 仓库。把这个仓库视为 self-contained runtime：以 `.journal/config.toml`、`AGENTS.md`、`docs/method/*`、`scripts/*`、memory、schemas、rubrics 和 templates 作为权威指令。原始 Skill 只用于安装、升级、修复或演进工作流。

生成的叙述性正文使用配置中的 `journal.language`；源码标识、路径、命令和 evidence ID 保持原样。

1. 读取 `.journal/config.toml`、`AGENTS.md`、active memory、`memory/candidates.yaml`、`memory/session-briefing.md`，以及 `docs/method/daily-runtime.md` 和 `docs/method/report-contract.md`。
2. 按配置的 IANA timezone 计算前一个本地自然日。按配置回看最近几天，但不要重写已经验证过的历史报告，除非新证据或 collector 修正确实改变了它。
3. 对每个需要采集的日期运行 `python3 scripts/collect_day.py --root . --date YYYY-MM-DD --json`。把它生成的 `collection.json` 和 `sources/` 下 provider-native 文件作为采集基线。collector 报告不完整时，不要声称该 source complete。
4. 检查允许持久化的完整上下文：可用时通过 App Server 读取 Codex sessions，读取 Claude Code 本地 JSONL、hook events、Git 仓库状态、tool calls、tests、documents、URLs、MCP resources、manual notes 和相关历史工作。只有在基线暴露出有理由的缺口时才额外采集证据。
5. collector 已经按所选 privacy level 处理持久化 source 文件。任何额外持久化也要应用同一等级。永远不要存储 credentials 或 authentication secrets。
6. 先生成 `evidence.json`，包含稳定 evidence IDs、source coverage、hashes、adapter/tool/model versions 和 historical context references。
7. 生成 `report.md` 时分离事实与分析。协作分析和评价是必需的；“做得好的地方”和“值得改进”是可选且必须由证据支持。不要把采集失败写成 `no-activity`。
8. 为多日连续性只检索相关历史报告和 memory。在这次 daily run 中维护四层记忆：L0 是 dated archive，L1 是 `memory/candidates.yaml`，L2 是 operational memory files，L3 是 `memory/session-briefing.md`。必要时根据 evidence、confidence、`first_seen` 和 `last_seen` promote/update/merge/reject/stale candidates。不要把整份 report dump 到 memory。
9. 在 daily run 中只根据已维护 memory 重新生成 `memory/session-briefing.md`。它必须在未来任何 `SessionStart` 前准备好；hooks 不得按需合成。保持它紧凑，标注为可修订上下文，并尽可能不超过 `memory.briefing_char_limit`。如果超过目标预算，在本次 daily run 中 compact。绝不能超过 `memory.briefing_hard_limit`。
10. daily job 不做宽泛 web research。只有重复摩擦、新任务类型、工具变化或 active experiment 证明有必要时，才新增 radar candidate。
11. 写入 `run.json`，运行 `python3 scripts/validate_journal.py --root .`，并在安全时修复确定性的 validation failures。
12. 只提交 journal-owned changes，commit message 使用 `journal: YYYY-MM-DD daily reflection`。按 policy push。push 失败时保留本地 commit 并更新 pending-push state。
13. daily artifact 安全后，检查 review boundaries。如果应有的 weekly 或 monthly review 到期且缺失，在同一次 unattended run 中执行对应 automation prompt，单独验证并提交。这样一个 durable daily scheduler 就能推动完整系统运行。

这是无人值守运行。不要询问常规问题。source 或 permission 不可用时，生成尽可能完整且诚实的报告，并记录 `missing evidence` 与准确失败阶段。
