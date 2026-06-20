# Validation Record

## Deterministic suite

- 46 standard-library tests passed across 10 modules.
- Coverage includes bootstrap/install upgrades, explicit install approval gating, lightweight language template selection, self-contained deployed runtime prompts, Git identity and pending push behavior, Hook capture, default-off precomputed SessionStart memory injection, Claude JSONL discovery, Codex App Server pagination/fallback/continuous process cleanup, Git snapshots, privacy transforms, scheduler rendering, historical backfill selection, and daily artifact validation.
- Python bytecode compilation passed for all scripts and tests.
- `scripts/validate_skill.py .` passed with `0` errors and `0` warnings.

The test modules were executed separately because the validation host limits the duration of a single shell command. Every module completed successfully; no failing module was omitted.

## End-to-end isolated deployment

A generated journal was installed with:

- sources: Codex + Claude Code;
- privacy: Low;
- timezone: Asia/Shanghai;
- daily time: 02:00;
- scheduler: Codex Automation, left honestly at `awaiting-user-confirmation`;
- additive user-scope Hooks;
- Git initialization and automatic local commits.

The smoke environment supplied a protocol-compatible Codex App Server fixture, a Claude Code JSONL session, Hook events, bounded memory, a precomputed session briefing, and a Git worktree. The collector produced:

- status: `active`;
- coverage: `complete`;
- Codex native coverage: `complete`;
- Claude native coverage: `complete`;
- Git coverage: `complete`;
- five Hook events;
- evidence-linked `report.md`, `evidence.json`, `run.json`, `collection.json`, and provider-native source artifacts.

`validate_journal.py` returned `valid: true`, `errors: 0`, `warnings: 0`. A `SessionStart` event received the precomputed bounded memory briefing only when injection was enabled, while a deliberately supplied credential assignment was replaced with `[REDACTED_SECRET]`. A separate test confirmed that SessionStart does not synthesize a briefing from L2 memory files. The durable repository contained none of the injected credential literals.

A daily commit was created with message:

```text
journal: 2026-06-20 daily reflection
```

Two identical installer reruns produced no Hook backups, no conflicts, a clean worktree, the same Git `HEAD`, and `git.commit = no-change` on the second run.

## Environment gates still open

This validation does not claim native production proof for:

- creating and firing a real Codex Automation in the user's desktop client;
- a real Claude Desktop scheduled task;
- reading the user's actual Codex/Claude histories and company repositories;
- authenticating and pushing to the user's company Git remote.

Those remain mandatory install-time smoke checks and are surfaced as explicit status, never inferred as complete.
