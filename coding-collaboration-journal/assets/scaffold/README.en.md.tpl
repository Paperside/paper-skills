# ${JOURNAL_NAME}

This repository is a long-running AI coding collaboration journal created by the `coding-collaboration-journal` skill.

At `${DAILY_TIME}` in `${TIMEZONE}`, it reviews the previous day of Codex / Claude Code activity, preserves an evidence trail across conversations, repositories, code changes, tests, resources, and decisions, and maintains compact long-term patterns and improvement experiments.

## Current configuration

- Sources: `${SOURCES}`
- Privacy level: `${PRIVACY}`
- Scheduler: `${SCHEDULER}`
- Automatic Git sync: `${AUTO_SYNC}`
- External practice radar: `${RADAR}`

## Memory

Daily runs maintain memory automatically: L1 candidates in `memory/candidates.yaml`, L2 operational memory files, and the precomputed L3 briefing in `memory/session-briefing.md`.

Beta `SessionStart` memory injection is disabled by default. When enabled in `.journal/config.toml`, the hook reads only the precomputed briefing, redacts it again, and caps it before injecting context. It does not generate memory on demand during interactive coding.

## Common operations

```bash
python3 scripts/doctor.py --root .
python3 scripts/collect_day.py --root . --date YYYY-MM-DD --json
python3 scripts/validate_journal.py --root .
python3 scripts/run_journal.py daily
python3 scripts/run_journal.py weekly
python3 scripts/run_journal.py monthly
```

Add manual observations to `.journal/notes/YYYY-MM-DD.md`; the next run will include them as evidence. When correcting a report, retain the original evidence references and record the reason in `run.json`.

## Layout

```text
journal/YYYY/MM/YYYY-MM-DD/   Daily reports and evidence
reviews/weekly/               Weekly reflections
reviews/monthly/              Monthly reflections
memory/                       Compact, editable long-term memory
radar/                        External practices and tool updates
.journal/events/              Hook event index
.journal/state/               Run, scheduler, and failure state
```

## Scheduler note

`${SCHEDULER_NOTE}`
