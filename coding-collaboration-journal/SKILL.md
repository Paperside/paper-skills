---
name: coding-collaboration-journal
description: Install, configure, deploy, run, repair, or evolve a persistent AI coding collaboration journal for Codex and Claude Code. Use when a user wants automatic daily work summaries, complete conversation/repository/resource context, long-term memory, evidence-grounded collaboration analysis, growth feedback, best-practice comparison, scheduled reflection, or a self-maintaining Git-backed engineering journal.
---

# Coding Collaboration Journal

## Router Rules

- Use this skill for system setup, migration, daily/weekly/monthly runs, backfills, diagnostics, and workflow evolution.
- Do not reduce this to a one-off chat summary when the user wants durable accumulation.
- Keep this file lean. Read only the references needed for the current mode.
- Prefer evidence completeness over aggressive abstraction. Never persist credentials, authentication material, or private keys.

## First-Turn Experience

Start with a plain-language explanation in the user's language:

> This creates a private Git-backed record of how you and your coding agents work together. It quietly gathers relevant Codex and Claude Code sessions, repositories, changes, tests, and referenced resources; then writes evidence-linked daily reflections and maintains longer-term patterns and improvement experiments.

Inspect the environment before asking questions, but do not install yet. Inferred values are recommendations only; they are not user approval. Before running any command that writes files, initializes Git, installs hooks, renders an active scheduler, commits, or pushes, present a compact install plan and wait for explicit user confirmation.

The pre-install plan must list every configurable item, available choices where relevant, the recommended default, and the detected/current value:

1. journal repository local path and remote URL (or permission to create them);
2. sources: Codex, Claude Code, or both;
3. timezone and daily run time (default `02:00` local time, reporting the previous day);
4. privacy level: `Low`, `Medium`, or `High` (recommend and default to `Low`);
5. scheduler choice;
6. automatic commit/push policy and remote sync target;
7. hooks: disabled, user-scope, or project-scope;
8. language template;
9. external-practice radar cadence;
10. memory settings, especially Beta `SessionStart` injection;
11. Git author name/email only when automatic commits are selected and no effective identity is configured.

When recommending **Codex Automations**, explicitly explain that project-scoped runs require the computer to be powered on, Codex to be running, and the selected project to remain available on disk. Let the user choose. If unavailable or unsuitable, offer the fallbacks in [Scheduler](references/scheduler.md).

Use a status checklist before asking for approval, for example `✅ verified`, `❌ missing/action required`, and `ℹ️ needs confirmation`. The checklist must include environment readiness, repository location/name, remote sync decision and URL, scheduler, hooks, privacy, language, memory injection, and Git identity. Do not treat a recommendation as acceptance; the user must clearly confirm the plan.

## Modes

- `install`: guided, idempotent setup and deployment.
- `daily`: collect yesterday's evidence, reconcile recent days, analyze, write, validate, commit, and push.
- `weekly`: consolidate patterns, experiments, and targeted external practices.
- `monthly`: compare like-for-like work, assess growth with uncertainty, and refresh goals.
- `note`: record a user's manual observation or correction without waiting for the scheduled run.
- `doctor`: diagnose missing sessions, broken hooks, scheduler failures, or Git sync issues.
- `evolve`: improve the generated journal workflow, rubric, adapters, or memory based on accumulated evidence.

## Install Workflow

1. Read [Onboarding](references/onboarding.md) and inspect OS, Git, Codex, Claude Code, timezone, existing skills, settings, and candidate repository paths.
2. Present the pre-install checklist and install plan. Recommend `Low` privacy and Codex Automations, but never silently choose any repository path, remote sync target, scheduler, hook scope, Git sync policy, or memory injection setting.
3. Wait for explicit user confirmation of the plan. If the user changes any material choice, show the revised plan before installing.
4. Run `scripts/bootstrap.py --yes` to create or upgrade the journal repository scaffold. Preserve user edits and make upgrades idempotent. `--dry-run` may be used before approval, but any non-dry-run install requires `--yes`.
5. Configure selected source adapters using [Source Adapters](references/source-adapters.md). Merge hook settings; never overwrite unrelated hooks or settings.
6. Configure the selected scheduler from [Scheduler](references/scheduler.md).
7. Run a dry collection and generate a sample report for a real or synthetic date.
8. Run `scripts/doctor.py`, `scripts/validate_journal.py`, and any repository tests.
9. Show exactly what was installed, what could not be verified, and any operational conditions.
10. Before automatic commits, verify an effective Git author identity; accept existing Git config or environment identity, and use repository-local `user.name`/`user.email` when the user supplies overrides.
11. Commit and push only after validation. If a remote or credentials are unavailable, leave a clean local commit and exact next action.

## Daily Operating Contract

Follow [Daily Runtime](references/daily-runtime.md) and [Report Contract](references/report-contract.md).

- Use the configured IANA timezone and a half-open reporting window `[day 00:00, next day 00:00)`.
- Reconcile the configured recent-day window to catch cross-midnight and delayed events.
- Collect complete permitted context from conversations, repositories, tool calls, tests, documents, URLs, and linked prior work.
- Separate facts, interpretations, evaluation, and recommendations.
- Attach stable evidence IDs to consequential claims.
- Always include collaboration analysis and an evaluation. Include “done well” and “could improve” only when supported.
- Distinguish `no-activity` from `incomplete-collection`.
- Continue multi-day work by retrieving relevant history rather than rereading the entire archive.
- Update bounded operational memory automatically; keep raw history in the dated archive.
- Do not manufacture a daily growth score.
- Validate, commit, and push. Record push failures for retry instead of losing the report.

## Long-Term Learning Contract

Read [Memory Model](references/memory-model.md), [Analysis Method](references/analysis-method.md), and [External Practice Radar](references/external-practice-radar.md).

- Treat memory as curated, revisable working knowledge—not a transcript dump.
- Maintain memory candidates, operational memory, and the precomputed session briefing during scheduled report runs.
- Treat Beta `SessionStart` injection as opt-in and disabled by default; when enabled, inject only the bounded, sanitized `memory/session-briefing.md`.
- Retrieve dated evidence when details matter.
- Promote a recurring pattern only after repeated evidence or one high-impact event.
- Store counter-evidence and confidence alongside claims.
- Turn improvement advice into bounded experiments with a hypothesis, intervention, metric, comparison set, and review date.
- Compare similar task classes and record model/tool/rubric versions to reduce evaluator drift.
- Use web research selectively: repeated friction, a new task class, a relevant tool change, or an active experiment. Prefer primary and official sources.
- Durable changes to the journal's `AGENTS.md`, `CLAUDE.md`, skills, rubric, or automation should be proposed with evidence; low-risk memory updates may be automatic according to configuration.

## Privacy Contract

Apply [Privacy Levels](references/privacy-levels.md).

- `Low` (recommended): retain detailed project, repository, file, conversation, tool, and resource context; remove credentials and authentication secrets only.
- `Medium`: additionally redact or alias commercial-sensitive values, customer/user identifiers, internal endpoints, and selected business data while preserving technical causality.
- `High`: omit raw transcripts and implementation identifiers; abstract repositories, files, services, and code into idea-level descriptions.
- Never silently downgrade information completeness beyond the selected level. Record every material redaction or unavailable source in coverage metadata.

## Failure Boundary

- Never label collection failure as “no work”.
- Never claim a hook, scheduler, remote push, App Server reader, or Claude transcript reader works without a smoke test.
- Codex hook transcript paths are discovery aids, not a stable parser contract. Prefer App Server for canonical Codex reads.
- Preserve existing settings and back them up before edits.
- Mark unavailable proof as `missing evidence`; do not fill gaps with plausible prose.

## Output Contract

For installation or substantial upgrades, leave:

- a runnable journal repository;
- `.journal/config.toml` and source/scheduler status;
- Codex and/or Claude Code adapter configuration;
- daily, weekly, and monthly automation prompts;
- report, evidence, memory, pattern, and experiment contracts;
- validation/doctor output;
- a scheduler setup or a precise user-visible final step;
- a Git commit and push when authorized and available.

## Reference Map

- [Architecture](references/architecture.md)
- [Onboarding](references/onboarding.md)
- [Source Adapters](references/source-adapters.md)
- [Scheduler](references/scheduler.md)
- [Daily Runtime](references/daily-runtime.md)
- [Report Contract](references/report-contract.md)
- [Privacy Levels](references/privacy-levels.md)
- [Memory Model](references/memory-model.md)
- [Analysis Method](references/analysis-method.md)
- [External Practice Radar](references/external-practice-radar.md)
- [Research Notes](references/research-notes.md)
