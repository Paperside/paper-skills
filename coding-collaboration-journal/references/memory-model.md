# Memory Model

## Goal

Let the system become more useful without turning every session into an ever-growing prompt. Keep a compact, curated operational memory and an unlimited dated archive.

## Memory Surfaces

### `memory/candidates.yaml`

Potential memory updates that are not yet durable knowledge:

- new preference or workflow claims;
- project continuity updates that need confirmation;
- recurring friction or improvement opportunities;
- stale facts that may need retirement;
- rejected candidates with brief rationale when useful for avoiding churn.

Daily runs review this file first, then promote, merge, reject, or stale candidates with evidence IDs, confidence, `first_seen`, and `last_seen` where applicable.

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

### `memory/session-briefing.md`

The precomputed L3 briefing for optional `SessionStart` injection. It is regenerated during the daily run from maintained L1/L2 memory only. It should be compact, labeled as revisable context, and useful as navigation rather than proof.

The target budget is `memory.briefing_char_limit` (default `6000`). The hard limit is `memory.briefing_hard_limit` (default `10000`). Daily maintenance should compact the briefing before finishing when it grows past the target budget, and validation rejects content beyond the hard limit.

## Automatic Memory Policy

Safe automatic writes:

- project/session continuity pointers;
- open-loop updates;
- explicit user preferences;
- new evidence attached to existing patterns;
- experiment observations;
- candidate promotion, rejection, merge, and staleness decisions;
- regeneration or compaction of `memory/session-briefing.md`;
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
- Compact memory during daily maintenance while retaining evidence pointers.

## Session-Start Briefing

Session-start memory injection is Beta and disabled by default. The hook never synthesizes memory from L2 files on demand. When `memory.inject_on_session_start = true`, it reads only the precomputed `memory/session-briefing.md`, sanitizes it, caps it, and emits it through `hookSpecificOutput.additionalContext`.

Default behavior:

- maintain L1/L2/L3 memory automatically during the daily run;
- regenerate `memory/session-briefing.md` during daily maintenance, even when injection is disabled;
- inject nothing unless `memory.inject_on_session_start = true`;
- load only meaningful, non-placeholder `memory/session-briefing.md`;
- apply the selected privacy policy and mandatory credential redaction again;
- cap the injected briefing at `memory.briefing_char_limit` as a last-resort runtime safety belt;
- label the briefing as revisable context, not an instruction to override the current user or repository;
- inject nothing when the briefing is empty, placeholder-only, or disabled by configuration.

The dated archive remains the source of truth. The briefing is a navigation and behavior aid, not evidence for a new claim.

## Retrieval

Load only:

- relevant project entries;
- active patterns implicated by current evidence;
- active experiments for the current task class;
- open loops linked to the current work;
- explicit user preferences relevant to the run.

This mirrors a Hermes-like separation: a bounded curated memory for immediate behavior, plus separate session/history search for details.
