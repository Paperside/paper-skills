# ${JOURNAL_NAME}

这是由 `coding-collaboration-journal` Skill 创建的长期 AI 编程协作档案。

它会在 `${DAILY_TIME}`（`${TIMEZONE}`）总结前一天的 Codex / Claude Code 工作，保存会话、仓库、代码变化、测试、资源与决策的证据链，并维护长期协作模式和改进实验。

## 当前配置

- 数据源：`${SOURCES}`
- 隐私等级：`${PRIVACY}`
- 调度方式：`${SCHEDULER}`
- 自动 Git 同步：`${AUTO_SYNC}`
- 外部实践雷达：`${RADAR}`

## 常用操作

```bash
python3 scripts/doctor.py --root .
python3 scripts/collect_day.py --root . --date YYYY-MM-DD --json
python3 scripts/validate_journal.py --root .
python3 scripts/run_journal.py daily
python3 scripts/run_journal.py weekly
python3 scripts/run_journal.py monthly
```

手动补充观察：在 `.journal/notes/YYYY-MM-DD.md` 记录，下一次运行会纳入证据。修正报告时，请保留原证据引用并在 `run.json` 记录修订原因。

## 目录

```text
journal/YYYY/MM/YYYY-MM-DD/   每日报告与证据
reviews/weekly/               周复盘
reviews/monthly/              月复盘
memory/                       紧凑、可编辑的长期记忆
radar/                        外部实践与工具更新
.journal/events/              Hook 采集事件
.journal/state/               运行、调度与失败状态
```

## 调度说明

`${SCHEDULER_NOTE}`
