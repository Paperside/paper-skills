# Memory Model

## Goal

Let the system become more useful without turning every session into an ever-growing prompt. Keep a compact, curated operational memory and an unlimited dated archive.

## Memory Surfaces

### `memory/user-profile.md`

Stable or explicitly stated preferences:

- preferred planning depth;
- desired autonomy;
- communication style;
- validation expectations;
- recurring constraints;
- how the user prefers Codex vs Claude Code to divide work.

Each non-explicit inference needs evidence and confidence.

### `memory/project-index.yaml`

Project aliases, repository roots/remotes, current goals, key documents, active branches, and continuity pointers. This is navigation, not analysis.

### `memory/collaboration-patterns.yaml`

Example:

```yaml
- id: P-007
  claim: Acceptance criteria are often added after implementation begins.
  status: suspected
  confidence: medium
  first_seen: 2026-06-03
  last_seen: 2026-06-19
  evidence:
    - 2026-06-03:E-CODEX-18
    - 2026-06-19:E-CLAUDE-42
  counterevidence:
    - 2026-06-12:E-CODEX-01
  impact: Rework and direction changes.
  next_review: 2026-07-01
```

Statuses:

```text
suspected → confirmed → improving → resolved
                     ↘ rejected
```

Promote to `confirmed` after repeated independent evidence, or one high-impact event with strong proof. Never delete counter-evidence.

### `memory/experiments.yaml`

Advice becomes useful only when testable:

```yaml
- id: E-004
  hypothesis: A first-prompt definition-of-done reduces corrective turns.
  intervention: Use templates/task-brief.md for comparable bug-fix tasks.
  task_class: bugfix
  metric: corrective_turns_before_validation
  baseline:
    sample_size: 8
    median: 3
  target:
    sample_size: 10
    median_at_most: 1
  start_date: 2026-06-20
  review_date: 2026-07-20
  status: active
```

### `memory/open-loops.yaml`

Unfinished tasks with minimal recovery context:

- intended outcome;
- current state;
- blocking question;
- latest evidence/report;
- next useful action;
- expiration/staleness date.

## Automatic Memory Policy

Safe automatic writes:

- project/session continuity pointers;
- open-loop updates;
- explicit user preferences;
- new evidence attached to existing patterns;
- experiment observations;
- staleness markers.

Default proposal-gated writes:

- new cross-project behavioral rules;
- modifications to `AGENTS.md` or `CLAUDE.md`;
- new skills or hook behavior;
- scheduler and permission changes;
- rubric changes that affect trend interpretation.

The user may configure a more autonomous policy, but every durable workflow mutation needs a Git diff, rationale, evidence IDs, and rollback commit.

## Memory Hygiene

- Prefer one durable statement over repeated daily paraphrases.
- Merge near-duplicates.
- Mark stale facts instead of silently carrying them forever.
- Keep source dates and confidence.
- Distinguish “user said” from “system inferred”.
- Do not store a personality diagnosis.
- Do not interpret rest days as motivation or performance signals.
- Periodically compact memory while retaining evidence pointers.

## Session-Start Briefing

The installed `SessionStart` hook turns the bounded memory files into one compact briefing for both Codex and Claude Code. It is emitted through `hookSpecificOutput.additionalContext`, so the agent receives useful continuity without replaying raw history.

Default behavior:

- load only meaningful, non-placeholder memory surfaces;
- apply the selected privacy policy and mandatory credential redaction again;
- cap the injected briefing at `memory.briefing_char_limit` (default `6000`, hard maximum `10000`);
- label the briefing as revisable context, not an instruction to override the current user or repository;
- inject nothing when memory is empty or `memory.inject_on_session_start = false`.

The dated archive remains the source of truth. The briefing is a navigation and behavior aid, not evidence for a new claim.

## Retrieval

Load only:

- relevant project entries;
- active patterns implicated by current evidence;
- active experiments for the current task class;
- open loops linked to the current work;
- explicit user preferences relevant to the run.

This mirrors a Hermes-like separation: a bounded curated memory for immediate behavior, plus separate session/history search for details.
