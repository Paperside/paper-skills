# Daily Automation Prompt

Operate this installed journal repository in **daily** mode. Treat the repository as the self-contained runtime: use `.journal/config.toml`, `AGENTS.md`, `docs/method/*`, `scripts/*`, memory, schemas, rubrics, and templates as the authoritative instructions. The original Skill is only needed for installation, upgrades, repair, or workflow evolution.

1. Read `.journal/config.toml`, `AGENTS.md`, active memory, `memory/candidates.yaml`, `memory/session-briefing.md`, and `docs/method/daily-runtime.md` plus `docs/method/report-contract.md`.
2. Compute the previous calendar day in the configured IANA timezone. Reconcile the configured recent days, but do not rewrite a validated historical report unless new evidence or a collector correction changes it.
3. For each date that needs collection, run `python3 scripts/collect_day.py --root . --date YYYY-MM-DD --json`. Treat its `collection.json` and provider-native files under `sources/` as the collection baseline. Never call a source complete when the collector reports otherwise.
4. Inspect the complete permitted context: Codex sessions through App Server when available, Claude Code local JSONL, hook events, Git repository state, tool calls, tests, documents, URLs, MCP resources, manual notes, and relevant prior work. Collect additional evidence only when the baseline exposes a justified gap.
5. The collector already applies the selected privacy level to durable source files. Apply the same level to any additional persistence. Credentials and authentication secrets are never stored.
6. Build `evidence.json` first with stable evidence IDs, source coverage, hashes, adapter/tool/model versions, and historical context references.
7. Generate `report.md` with facts separated from analysis. Collaboration analysis and evaluation are mandatory; “done well” and “could improve” are optional and evidence-gated. Never turn collection failure into `no-activity`.
8. Retrieve only relevant historical reports and memory for multi-day continuity. Maintain the four memory layers during this daily run: L0 is the dated archive, L1 is `memory/candidates.yaml`, L2 is the operational memory files, and L3 is `memory/session-briefing.md`. Promote/update/merge/reject/stale candidates with evidence, confidence, `first_seen`, and `last_seen` where applicable. Do not dump the report into memory.
9. Regenerate `memory/session-briefing.md` during the daily run from maintained memory only. It must be ready before any future `SessionStart`; hooks must not synthesize it on demand. Keep it compact, labeled as revisable context, and at or below `memory.briefing_char_limit` when possible. If it grows beyond that target, compact it during this daily run. It must never exceed `memory.briefing_hard_limit`.
10. Do not run broad web research during the daily job. Add a radar candidate when repeated friction, a new task class, a tool change, or an active experiment justifies it.
11. Write `run.json`, run `python3 scripts/validate_journal.py --root .`, and resolve deterministic validation failures where safe.
12. Commit only journal-owned changes using `journal: YYYY-MM-DD daily reflection`. Push according to policy. If push fails, preserve the local commit and update pending-push state.
13. After the daily artifact is safe, check review boundaries. If the configured weekly or monthly review is due and missing, execute the corresponding automation prompt in the same unattended run, with its own validation and commit. This lets one durable daily scheduler keep the full system moving.

This is an unattended run. Do not ask routine questions. When a source or permission is unavailable, produce the most complete honest report possible and record `missing evidence` plus the exact failed stage.
