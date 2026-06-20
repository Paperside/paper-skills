# Source Adapters

The analysis pipeline must not care whether evidence came from Codex or Claude Code. Each adapter discovers sessions, reads canonical records, normalizes evidence, and reports coverage.

## Shared Adapter Contract

```text
probe() -> availability, version, permissions, warnings
list_activity(start, end) -> session references
read_session(ref) -> provider-native full record
normalize(record, privacy) -> evidence items
coverage() -> complete | partial | unavailable
```

Every adapter records:

- adapter version;
- provider/tool version;
- discovered session IDs;
- read failures;
- time bounds used;
- whether data came from a stable or fallback interface.

The installed journal invokes these adapters through `scripts/collect_day.py`. This keeps session discovery and date-window rules deterministic instead of asking the analysis model to rediscover provider storage on every run.

For repository discovery, provider readers may be invoked transiently with the `Low` structural representation after mandatory credential removal, so working-directory paths remain available to the orchestrator. Before any provider payload is persisted, `collect_day.py` reapplies the user's selected Low/Medium/High policy. This transient step must never write a lower-privacy artifact to disk.

## Codex

### Discovery Index: Hooks

Install additive command hooks for at least:

- `SessionStart`;
- `UserPromptSubmit`;
- `PostToolUse`;
- `Stop`;
- `SubagentStart` and `SubagentStop` when available.

Suggested user-level `~/.codex/hooks.json` fragment, with the absolute journal path substituted:

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source codex --root /ABS/JOURNAL"
      }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source codex --root /ABS/JOURNAL"
      }]
    }],
    "PostToolUse": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source codex --root /ABS/JOURNAL"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source codex --root /ABS/JOURNAL"
      }]
    }]
  }
}
```

Merge by event and handler identity. Do not replace existing groups. After writing, use Codex `/hooks` or the current trust UI to review and trust the command; then generate one prompt and one tool call and verify two events were appended.

Hooks provide `session_id`, `cwd`, event name, model, and usually `transcript_path`; turn events include `turn_id`. `UserPromptSubmit` includes the prompt. Treat `transcript_path` as a discovery pointer only because its file format is not a stable hook interface.

Codex `PostToolUse` is supplemental rather than exhaustive: current hooks do not intercept every shell execution path and do not cover WebSearch or every non-shell/non-MCP tool. Never infer complete activity coverage from hook events alone.

### Canonical Reader: App Server

Preferred flow:

1. start `codex app-server --listen stdio://`;
2. send one newline-delimited JSON `initialize` request; keep `capabilities.experimentalApi = true` as backward compatibility for older Codex builds that gated paged turn history, while using only documented methods;
3. send the `initialized` notification;
4. page the stable `thread/list` interface by recency, including archived threads by default; explicitly request all documented source kinds (`cli`, `vscode`, `exec`, `appServer`, subagent variants, and `unknown`);
5. if an installed version rejects the explicit source set, retry with its interactive-source default, mark coverage `partial`, and never present that fallback as all-source coverage;
6. stop when timestamps are older than the reconciliation window; guard against repeated cursors and deduplicate thread IDs across active/archived pages;
7. read each qualifying thread through stable `thread/read(includeTurns: true)`;
8. page the currently documented `thread/turns/list` interface with `itemsView: "full"` to prove complete pagination;
9. if paged turn reading fails, retain the stable `thread/read` history, record a warning, and do not replace it with a known-partial page set;
10. normalize messages, commands, file changes, tool calls, approvals, URLs, model, cwd, and Git metadata.

Use both human and agent activity semantics:

- `human_active`: a user message occurred in the report window;
- `agent_active`: an agent/tool item occurred in the report window;
- `context_only`: an older thread was retrieved because today's work references it.

### Fallback Reader

If App Server cannot start, stable `thread/list`/`thread/read` are unavailable, or the installed version cannot enumerate the required source kinds:

- use hook-indexed transcript paths or documented local rollout storage;
- copy the full provider-native file into the evidence pack at Low privacy;
- mark `interface_stability = "fallback-unstable"`;
- do not write a complete-coverage claim.

## Claude Code

### Discovery Index: Hooks

Claude Code command hooks receive JSON on stdin. Install additive hooks in `~/.claude/settings.json` for global coverage, or project settings when required by company policy.

Suggested fragment:

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source claude --root /ABS/JOURNAL"
      }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source claude --root /ABS/JOURNAL"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source claude --root /ABS/JOURNAL"
      }]
    }],
    "PostToolUseFailure": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source claude --root /ABS/JOURNAL"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source claude --root /ABS/JOURNAL"
      }]
    }],
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "/usr/bin/python3 /ABS/JOURNAL/scripts/capture_event.py --source claude --root /ABS/JOURNAL"
      }]
    }]
  }
}
```

Use a platform-appropriate Python executable on Windows. Keep hook commands fast and non-blocking; `capture_event.py` must exit zero even when logging fails.

### Canonical Reader: Local Session JSONL

Claude Code stores CLI sessions continuously as local JSONL files, normally under `~/.claude/projects/<project>/<session-id>.jsonl`. The exact project directory encoding may vary; rely on hook `transcript_path` first and scan the documented root second.

For every active session:

1. find candidate files through hook-referenced transcript paths first, then a bounded modification-time scan of the documented session root; `collect_day.py` automatically enables a full `--scan-all` pass for dates older than the configured reconciliation horizon, and it can be forced with `--scan-all-claude`;
2. scan embedded timestamps across the complete candidate file even when the durable provider-native payload is size-bounded, so activity in the middle of a large JSONL is not missed;
3. copy or read the full JSONL file when it fits the configured evidence limit;
4. preserve record order;
5. select report-window events by embedded timestamps where available;
6. retain surrounding messages needed to understand the selected work;
7. include tool inputs and responses at Low privacy;
8. discover subagent transcript references and include them when relevant;
9. record whether the session came from CLI, Desktop, web, or IDE when detectable, because histories may be separate.

Daily copying prevents later loss from local transcript retention cleanup. The installer may suggest increasing Claude's cleanup period, but should not change it without approval.

## Git Repository Context

For each unique working directory discovered recursively from provider payloads, enabled hook events, or an explicit `--repo` override:

1. resolve Git root with `git rev-parse --show-toplevel`;
2. derive a stable repo ID from remote URL, root path, and an alias registry;
3. record remote aliases, current branch, start/end HEAD, worktree status, and stash state;
4. inspect commits whose author or committer time intersects the report window;
5. inspect reflog and working-tree changes to catch uncommitted work; label status and diffs as a collection-time snapshot because Git cannot reliably assign individual uncommitted edits to the report date;
6. summarize changed paths and diff stats; include full diffs according to privacy and size policy;
7. collect explicit test/build/lint commands and their results from agent records;
8. avoid claiming a code change succeeded solely because it was written.

## External Resources

Extract and index:

- URLs opened or cited;
- documentation titles and access dates;
- MCP server/tool names and arguments;
- local documents read;
- issue, PR, ticket, and design-document identifiers;
- images or screenshots that affected a decision;
- commands that fetched external content.

At Medium/High privacy, normalize these before persistence, not only before report rendering.

## Deduplication

The same action may appear in a hook event, provider transcript, and Git history. Keep all provenance but assign one canonical action cluster:

```json
{
  "cluster_id": "A-20260620-0042",
  "primary": "E-GIT-...",
  "supporting": ["E-CODEX-...", "E-HOOK-..."],
  "relationship": "agent_requested_and_git_observed"
}
```
