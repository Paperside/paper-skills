# Daily Runtime

## Date Window

At a run near 02:00, report the previous local calendar date:

```text
report_date = local_today - 1 day
start = report_date 00:00:00 in configured IANA timezone
end   = report_date + 1 day 00:00:00 in configured IANA timezone
window = [start, end)
```

Store UTC timestamps plus original offset. Never infer a day from file modification time alone.

## Run State Machine

```text
locked → preflight → collect → normalize → enrich → retrieve-history
       → analyze → render → validate → publish → complete
```

On failure, write `run.json` with the failed stage, error summary, and retryability.

## Procedure

### 1. Acquire Lock and Reconcile Git

- acquire `.journal/state/run.lock` without clobbering an active run;
- verify repository identity and branch;
- pull/rebase according to configured policy;
- retry pending pushes;
- refuse destructive conflict resolution.

### 2. Probe Sources

Run `doctor` probes for every enabled source. Record versions and availability before collection. Disabled sources are recorded as `coverage = disabled`; they are not collected, do not create provider files, and do not affect activity or completeness.

### 3. Collect Activity

Start with the deterministic collection entrypoint:

```bash
python3 scripts/collect_day.py --root . --date YYYY-MM-DD --json
```

For a deliberate older Claude Code backfill, the collector automatically scans the full local session store once the date falls outside the reconciliation horizon; `--scan-all-claude` forces that behavior explicitly. Treat its `collection.json` and `sources/*.json` as the baseline. The Agent may fill a justified gap, but must not silently override a collector's coverage status.

Collect:

- session/thread summaries that overlap the date or reconciliation horizon;
- full records for qualifying sessions;
- selected older context needed to understand active work;
- Git state for all discovered repositories; commits/reflog are date-window evidence, while uncommitted status and diffs are explicitly labeled as collection-time snapshots;
- referenced documents, URLs, MCP calls, issues, and PRs;
- manual notes for the report date.

### 4. Normalize and Redact

Apply privacy rules before writing durable evidence. Always remove credential material. Produce stable evidence IDs and content hashes.

### 5. Determine Activity Status

Use exactly one:

- `active`: qualifying human or agent work exists;
- `no-activity`: all enabled sources collected successfully and none contain qualifying activity;
- `incomplete-collection`: at least one required source failed or coverage is insufficient;
- `partial-activity`: activity exists, but one or more configured sources are incomplete.

A holiday or rest day is not a negative signal.

### 6. Retrieve Relevant History

Default retrieval order:

1. reports directly linked by session/thread continuation;
2. same repository and branch in the last 7 days;
3. same task/issue/PR identifiers in the last 30 days;
4. active open loops, patterns, and experiments;
5. older history only when the current evidence explicitly points to it.

Do not load the entire archive by default. Record every historical artifact used as context.

### 7. Build the Evidence Pack

Write `evidence.json` first. Include:

- source inventory and coverage;
- normalized evidence items;
- action clusters;
- repository snapshots;
- referenced history;
- redaction log;
- hashes and adapter versions.

### 8. Analyze

Follow the analysis rubric. Important distinctions:

- work attempted vs work completed;
- agent claim vs Git/test-observed result;
- user decision vs agent suggestion;
- local verification vs production/user outcome;
- process quality vs task difficulty;
- a one-off event vs a repeated pattern.

### 9. Update Memory

Memory maintenance happens during the daily run, including the precomputed L3 briefing. Do not defer memory synthesis to the next interactive session.

- treat the dated report and evidence pack as L0 archive;
- review `memory/candidates.yaml` as the L1 candidate layer;
- promote, update, merge, reject, or stale candidates with evidence IDs, confidence, `first_seen`, and `last_seen` where applicable;
- refresh L2 operational memory: project continuity, open loops, stable preferences, pattern evidence/counter-evidence, and experiment observations;
- regenerate L3 `memory/session-briefing.md` from maintained memory only, even though SessionStart injection is disabled by default;
- keep `memory/session-briefing.md` at or below `memory.briefing_char_limit` when possible, compact it during the daily run when it grows past that target, and never exceed `memory.briefing_hard_limit`;
- treat truncation at hook time as a last-resort failure boundary, not normal maintenance;
- never copy the whole report into memory.

### 10. Render and Validate

Render `report.md` deterministically from a structured analysis result where practical. Validate:

- required sections;
- evidence IDs resolve;
- coverage and status agree;
- dates and timezone agree;
- no forbidden secret pattern appears;
- optional sections are omitted rather than padded;
- report and evidence hashes are recorded in `run.json`.

### 11. Publish

Commit only files belonging to the journal run. Suggested commit:

```text
journal: 2026-06-19 daily reflection
```

Push and verify the remote ref. If push fails, keep the commit and record pending state.

## No-Activity Run

Generate a small but valid report:

```markdown
# 2026-06-19

## Status

No Codex or Claude Code human/agent activity was detected in the configured time window. All configured collectors completed successfully.

## Collaboration analysis

There is not enough activity evidence to assess collaboration behavior today. A rest day is not treated as regression.
```

## Incomplete Run

Be explicit:

```markdown
## Data quality

Claude Code evidence was collected, but the Codex App Server reader failed during pagination. This report may omit Codex work and must not be interpreted as a complete record of the day.
```
