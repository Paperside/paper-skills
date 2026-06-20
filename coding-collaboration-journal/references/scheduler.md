# Scheduler

## Decision Order

1. **Codex Automation** — preferred when available and its local-runtime conditions are acceptable.
2. **Claude Desktop scheduled task** — strong fallback when Claude is the primary runner and local files are required.
3. **Operating-system scheduler + non-interactive CLI** — most controllable cross-tool fallback.
4. **Cloud routine / CI** — only when all required evidence is available remotely or a self-hosted runner has local access.

Do not use an in-session loop as a durable daily scheduler.

## Option 1: Codex Automation (Recommended)

Use a project-scoped automation targeting the journal repository, ideally in an isolated worktree when supported. Schedule the generated `automation/daily.md` prompt at the configured local time.

Before the user chooses it, state these conditions plainly:

- the computer must be powered on;
- Codex must be running;
- the selected project must still exist at the configured disk path;
- the automation needs permission to read selected session stores and project repositories;
- Git credentials must be available for automatic push.

Suggested task name:

```text
AI Collaboration Journal — Daily
```

Suggested prompt:

```text
Operate this installed journal repository in daily mode. Read .journal/config.toml, AGENTS.md, docs/method/daily-runtime.md, docs/method/report-contract.md, and the generated automation/daily.md. Summarize the previous calendar day in the configured timezone, reconcile the configured recent days, update bounded memory, regenerate the precomputed session briefing, validate artifacts, and commit and push according to policy. Treat collection errors as incomplete-collection, never as no-activity.
```

Also create weekly and monthly tasks when requested. Keep the daily task responsible for data continuity; weekly/monthly tasks may safely skip when there is no new material.

### Verification

A configured Automation is not considered deployed until:

- it appears in the client task list;
- a manual test run completes;
- expected report/run artifacts are created;
- the Git commit exists;
- push status is verified or explicitly recorded as pending.

If the current client exposes no programmatic creation action, generate the exact task name, project, schedule, and prompt, then guide the user through the final UI confirmation. Mark scheduler status `awaiting-user-confirmation`, not `active`.

## Option 2: Claude Desktop Scheduled Task

Use when Claude needs local filesystem access and Desktop scheduling is available. Desktop scheduled tasks can persist across restarts and do not require an open Claude Code session, but the machine must be on.

Point the task at the journal repository and run the generated `automation/daily.md` prompt. Configure permissions for reading selected repositories and writing/committing the journal.

Avoid CLI `/loop` for the permanent daily job: it is session-scoped, requires an open session, and recurring tasks expire after a bounded period.

## Option 3: OS Scheduler

Use an OS scheduler to invoke a deterministic wrapper, which then launches the chosen agent non-interactively.

### macOS

Use `launchd`, not an interactive shell cron, when environment and login-session reliability matter. Generate a plist with:

- `StartCalendarInterval` at configured local time;
- working directory = journal repo;
- a wrapper that sets `PATH` explicitly;
- stdout/stderr under `.journal/state/logs/`;
- `RunAtLoad` only if desired.

### Linux

Prefer a user `systemd` timer:

- `OnCalendar=*-*-* 02:00:00`;
- `Persistent=true` to catch missed runs after wake/login;
- service working directory = journal repo;
- explicit environment file or login-independent executable paths.

### Windows

Use Task Scheduler with:

- local timezone schedule;
- “run as soon as possible after a scheduled start is missed”;
- working directory and executable paths fully qualified;
- credentials/interactive policy appropriate for Git access.

### Runner Command

Prefer an installed wrapper such as:

```bash
python3 scripts/run_journal.py daily
```

The wrapper can call `codex exec` or `claude -p` with the generated prompt. Detect current CLI syntax at install time; do not freeze undocumented flags into the skill.

## Option 4: Cloud / CI

Use only if the runtime can access all required data. A hosted GitHub runner normally cannot read local Codex/Claude histories or uncommitted local repositories. A self-hosted runner can, but then its availability and permissions become part of the operational contract.

## Retry and Idempotency

- Use a run lock keyed by report date.
- Regeneration writes to a temporary directory and atomically replaces artifacts after validation.
- Re-running a successful date should produce no commit when content is unchanged.
- Push failures enter `.journal/state/pending-push.json`; the next run retries before creating new commits.
- Reconcile the last 3 days by default to catch delayed and cross-midnight activity.
