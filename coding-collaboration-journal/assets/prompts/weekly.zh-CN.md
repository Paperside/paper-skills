# 每周自动化提示

以 **weekly** 模式运行这个已安装的 journal 仓库。把这个仓库视为 self-contained runtime：以 `.journal/config.toml`、`AGENTS.md`、`docs/method/*`、`scripts/*`、memory、schemas、rubrics 和 templates 作为权威指令。原始 Skill 只用于安装、升级、修复或演进工作流。

生成的叙述性正文使用配置中的 `journal.language`；源码标识、路径、命令和 evidence ID 保持原样。

1. 读取上一个已完成的本地周、active memory、patterns、experiments、radar candidates 和 report coverage。
2. 整理重复出现的协作行为并保留 counter-evidence。不要仅因为多份 daily reports 复述了同一个原始事件就 promote pattern。
3. 只比较相似 task classes，并说明 task difficulty、model/client/rubric epochs 和 evidence confidence。
4. 复查 active experiments：observations、sample size、confounders，以及应该继续、修订、关闭还是 reject。
5. 选择最多三个高杠杆改进。
6. 只对被触发的 radar candidates 做 targeted web research。优先 current official documentation、primary research、standards、maintainers' engineering material 和 reproducible evidence。将 source dates、access dates、applicability、limitations 和 citations 保存进 practice cards。
7. 更新 `reviews/weekly/YYYY-Www.md`、bounded memory、pattern state、experiment state 和 radar ledger。
8. 验证后提交，commit message 使用 `journal: YYYY-Www weekly review`，并按 policy push。

不要写泛泛的 productivity essay，也不要输出单一的个人表现分数。
