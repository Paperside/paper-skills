# Guided Onboarding

## Conversation Style

Use simple language and explain outcomes before implementation details. Do not interrogate the user one field at a time. Inspect first, then present inferred values and unresolved choices in one compact block.

Example:

> 我会给你建一个长期运行的 AI 编程协作日志：每天自动收集 Codex/Claude Code 会话、关联仓库和资源，写有证据引用的复盘，并维护长期模式与改进实验。下面这些我已经检测到了；只需要你确认没法安全推断的几项。

## Silent Preflight

Inspect without asking:

- operating system and Python version;
- IANA timezone where available;
- `git`, `codex`, and `claude` availability and versions;
- whether the current directory is a repository;
- likely journal repository paths;
- current Git remotes, authentication readiness, and effective Git author identity;
- `~/.codex/hooks.json`, Codex config layers, and hook feature state;
- `~/.claude/settings.json`, project Claude settings, and transcript root;
- existing scheduler support;
- whether an existing journal installation can be upgraded.

Do not print secret values while inspecting.

## Required Choices

Ask only what remains unresolved:

| Choice | Recommended default | Notes |
|---|---|---|
| Journal local path | `~/ai-collaboration-journal` | Prefer a dedicated repository. |
| Remote | user's private/company personal Git repo | May create or attach an existing empty remote. |
| Sources | all detected tools | Support `codex`, `claude`, or both. |
| Timezone | detected IANA zone | Never rely on a bare UTC offset for DST regions. |
| Daily time | `02:00` | Report the previous calendar day. |
| Privacy | `Low` | Full project context; credentials still removed. |
| Scheduler | Codex Automation | Explain operational conditions before confirmation. |
| Git sync | auto commit + push | Retry failures; never discard local artifacts. |
| Git author identity | existing Git identity | Ask only when automatic commits are selected and no effective identity exists; prefer a repository-local override when supplied. |
| External radar | weekly, targeted | Not a broad daily search. |
| Session memory injection | disabled | Beta opt-in; daily memory maintenance still runs automatically. |
| Language | user's language | `zh*` and `en*` select matching README/AGENTS/CLAUDE/report/automation templates; unsupported tags fall back to English templates while generated prose follows config. Keep source identifiers unchanged. |

## Privacy Explanation

Keep it practical:

- **Low（推荐）**：保留仓库名、文件名、对话、代码思路、工具输出和项目细节；只排除 token、密码、私钥、Cookie 等认证信息。
- **Medium**：再对客户、内部地址、业务数据和商业敏感值做别名或替换，但保留技术因果关系。
- **High**：不保存原始对话和实现标识，只保留抽象后的问题、方案、决策与方法。

Ask for a level; do not turn this into a generic security lecture.

## Scheduler Choice

Say this before asking the user to choose Codex Automation:

> 我推荐 Codex Automation，因为它能直接运行这个 Skill，并在本地项目里完成日报、Git commit 和 push。需要注意：项目型 Automation 运行时，电脑要开机、Codex 要保持运行，而且这个日志仓库仍要存在于选定路径。你可以选它，或者改用 Claude Desktop / 系统调度器。

## Autonomy Choice

Default policy:

```toml
[autonomy]
daily_reports = "automatic"
memory_updates = "automatic"
pattern_updates = "automatic"
experiment_proposals = "automatic"
workflow_file_changes = "proposal"
external_research = "automatic_when_triggered"
git_commit = "automatic"
git_push = "automatic"
```

Explain that the system may quietly maintain memory candidates, operational memory, and the precomputed session briefing during daily runs. Beta `SessionStart` injection remains off by default and only reads the precomputed briefing when explicitly enabled. Changes to `AGENTS.md`, `CLAUDE.md`, skills, rubric, or scheduler remain proposal-gated by default. The user may choose fully automatic workflow changes, but require a rollback commit and change log.

## Repository Setup

When the remote is new:

1. create or clone the local directory;
2. initialize Git if needed;
3. attach `origin` only after checking it is the intended repository;
4. default branch `main` unless the remote says otherwise;
5. create scaffold;
6. validate;
7. verify an effective Git author name and email; when absent, ask once and store any supplied values as repository-local config;
8. make one installation commit;
9. push and verify the remote ref.

When the repository already has content, inspect its conventions and install without deleting unrelated files.

## Completion Message

Report:

- local and remote repository;
- enabled sources and their smoke-test status;
- privacy level;
- scheduler and exact run time;
- memory maintenance status and whether Beta `SessionStart` injection is enabled;
- whether computer/app availability is required;
- latest successful dry-run date and artifact path;
- Git commit SHA and push status;
- any `missing evidence` or manual final action.
