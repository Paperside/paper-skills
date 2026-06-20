# 每月自动化提示

以 **monthly** 模式运行这个已安装的 journal 仓库。把这个仓库视为 self-contained runtime：以 `.journal/config.toml`、`AGENTS.md`、`docs/method/*`、`scripts/*`、memory、schemas、rubrics 和 templates 作为权威指令。原始 Skill 只用于安装、升级、修复或演进工作流。

生成的叙述性正文使用配置中的 `journal.language`；源码标识、路径、命令和 evidence ID 保持原样。

1. 读取已完成的本地月、weekly reviews、active 和 closed experiments、pattern history、model/tool/skill/rubric epochs，以及 data-quality gaps。
2. 只基于可比较的 task classes 和证据充分的趋势评估成长。区分可能的用户改进与 model、client、repository、task-mix 和 evaluator changes。
3. 识别 durable workflow gains、persistent friction、rejected assumptions 和 unresolved uncertainty。
4. 关闭、继续或重新设计 experiments。优先提出一两个具体的 next experiments，而不是长建议清单。
5. 对 `AGENTS.md`、`CLAUDE.md`、templates、hooks、automation 或本 journal 的 rubric 提出 evidence-backed changes。只在配置的 autonomy policy 允许时应用，并始终留下可回滚 Git diff。
6. 更新 `reviews/monthly/YYYY-MM.md`、goals、bounded memory 和 epoch records。
7. 验证后提交，commit message 使用 `journal: YYYY-MM monthly review`，并按 policy push。

明确说明现有证据无法支持哪些结论。
