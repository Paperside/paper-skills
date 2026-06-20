# Research Notes and Design Provenance

Last reviewed: 2026-06-20.

This file records the primary sources used to design the skill. Recheck them when provider behavior or configuration schemas change.

## OpenAI Codex

- Agent Skills: https://developers.openai.com/codex/skills
  - User skills live under `~/.agents/skills`; repository skills live under `.agents/skills`.
  - `agents/openai.yaml` carries optional Codex UI and invocation metadata.
  - Codex discovers skill edits automatically and supports symlinked skill folders.
- Codex Automations: https://developers.openai.com/codex/app/automations
  - Scheduled recurring work can be combined with skills.
  - Project-scoped automation requires the machine on, Codex running, and the selected project available on disk.
- Codex Hooks: https://developers.openai.com/codex/hooks
  - Lifecycle command hooks support session, prompt, tool, stop, compact, and subagent events.
  - Hook input exposes session ID, cwd, model, event name, and transcript path.
  - Transcript format is explicitly not a stable hook interface.
- Codex App Server: https://developers.openai.com/codex/app-server
  - `thread/list`, `thread/read(includeTurns=true)`, and paged `thread/turns/list` are currently documented interfaces.
  - `thread/list` defaults to interactive (`cli`, `vscode`) sources when `sourceKinds` is omitted; the reader explicitly requests every documented source kind and marks interactive-only fallback as partial.
  - The reader enables `experimentalApi` only for backward compatibility with older builds that gated paged turn history; stable `thread/read` remains the full-history fallback.
  - The stdio transport is newline-delimited JSON with initialize/initialized handshake.
- Codex non-interactive mode: https://developers.openai.com/codex/noninteractive

## Anthropic Claude Code

- Skills: https://code.claude.com/docs/en/skills
  - Personal skills live under `~/.claude/skills`; project skills live under `.claude/skills`.
- Hooks reference: https://code.claude.com/docs/en/hooks
  - UserPromptSubmit, PostToolUse, Stop, SessionEnd, subagent, and other events expose session/transcript context.
  - User and project settings locations are documented and must be merged rather than overwritten.
- Sessions: https://code.claude.com/docs/en/sessions
  - CLI sessions are stored continuously as JSONL under `~/.claude/projects/<project>/<session-id>.jsonl` (or `CLAUDE_CONFIG_DIR`).
  - Local transcript files are removed after 30 days by default unless `cleanupPeriodDays` changes; daily copying therefore protects continuity.
  - Different Claude surfaces may maintain separate session history.
- Memory: https://code.claude.com/docs/en/memory
  - CLAUDE.md holds durable instructions; auto memory holds learned patterns.
  - Concise, scoped memory is more reliable than loading everything.
- Scheduled tasks: https://code.claude.com/docs/en/scheduled-tasks
  - In-session loops are not durable daily scheduling.
  - Desktop tasks can access local files and persist across restarts but require the machine on.

## Hermes-Inspired Memory Model

- Hermes Agent repository: https://github.com/NousResearch/hermes-agent
- Persistent memory: https://hermes-agent.nousresearch.com/docs/user-guide/features/persistent-memory/
- Skills: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/

Borrowed principles:

- separate compact agent-curated memory from searchable session history;
- save durable preferences and recurring patterns, not raw ephemera;
- allow quiet background review with user-editable memory;
- use progressive disclosure for skills and references.

## Yao Meta Skill

- Repository: https://github.com/yaojingang/yao-meta-skill
- `SKILL.md`: https://github.com/yaojingang/yao-meta-skill/blob/main/SKILL.md
- `agents/interface.yaml`: https://github.com/yaojingang/yao-meta-skill/blob/main/agents/interface.yaml
- Skill IR: https://github.com/yaojingang/yao-meta-skill/tree/main/skill-ir

Borrowed principles:

- keep the skill entrypoint lean;
- put method in references and logic in scripts;
- define a platform-neutral semantic contract;
- include trigger/output evals and explicit evidence boundaries;
- mark unavailable proof as missing evidence rather than fabricating readiness.

Deliberately not copied:

- heavyweight release governance unrelated to a personal/company-internal journal;
- public “world-class” claim machinery;
- metadata-only telemetry, because this system intentionally prioritizes full authorized context at Low privacy.
