# AI Collaboration Journal Instructions

This repository is a durable evidence-backed record of the user's work with coding agents.

## Daily Rules

- Read `.journal/config.toml` before every run.
- Build evidence before writing conclusions.
- Preserve complete context allowed by the selected privacy level.
- Never persist credentials, authentication tokens, cookies, private keys, or secret-manager values.
- Treat Codex and Claude Code as different source adapters feeding one shared analysis model.
- Distinguish observed Git/test outcomes from claims in conversation.
- Always include collaboration analysis and evaluation; optional praise/improvement sections require evidence.
- `no-activity` requires successful collection from every enabled source. Otherwise use `incomplete-collection` or `partial-activity`.
- Retrieve relevant prior days for continuing work; do not load the whole archive without cause.
- Update L1 memory candidates, L2 operational memory, and L3 `memory/session-briefing.md` during the daily run without copying entire transcripts or reports into memory.
- Validate before commit. Preserve local commits when push fails.

## Autonomy

Follow `[autonomy]` in `.journal/config.toml`. Routine reports and memory maintenance may be automatic. Changes to this file, `CLAUDE.md`, hooks, scheduler, rubric, or installed skills are proposal-gated unless configuration explicitly permits automatic workflow changes.

## Report Paths

Use `journal/YYYY/MM/YYYY-MM-DD/` with numeric months. Weekly and monthly reviews live under `reviews/`.
