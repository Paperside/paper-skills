# Output Quality Scorecard

Review date: 2026-06-20

## Scope

This scorecard records what the package currently proves and what still requires a real client environment. Planned behavior is not treated as runtime evidence.

| Area | Status | Evidence | Residual gap |
|---|---|---|---|
| Lean routing entrypoint | Pass | `SKILL.md` routes install/daily/weekly/monthly/note/doctor/evolve and delegates detail to references. | Trigger behavior still depends on the host agent's skill router. |
| Platform-neutral contract | Pass | `skill-ir/skill.json`, `agents/interface.yaml`, `agents/openai.yaml`, shared evidence/report contracts. | No published registry conformance test yet. |
| Codex support | Implemented, environment verification required | App Server reader uses documented paged turn history, requests `experimentalApi` for older-build compatibility, and keeps `thread/read(includeTurns=true)` fallback; additive hooks, Automation prompt, doctor checks. | Requires a machine with Codex, hook trust, App Server compatibility, and an actual Automation run. |
| Claude Code support | Implemented, environment verification required | Local JSONL reader, additive hooks, Desktop task instructions, doctor checks. | Requires a machine with Claude Code/Desktop and real session files. |
| Privacy levels | Pass for deterministic transforms | Low/Medium/High policy plus secret redaction tests. | Business-sensitive classification at Medium remains partly configuration- and model-dependent. |
| Idempotent installation | Pass in local tests | Managed-file hashes, user-edit preservation, true upstream/user conflict candidates, stable scheduler/manifest timestamps, and verified `no-change` Git reruns. | Cross-generation migrations need fresh evidence as the repository evolves. |
| Daily artifact validation | Pass in local tests | Status consistency, evidence-ID integrity, false no-activity guard, secret-pattern scan. | Semantic truth of LLM analysis requires review/evals on real reports. |
| Long-term memory method | Locally evidenced contract | Candidate promotion, pattern counter-evidence, epochs, experiments, precomputed L3 briefing, default-off SessionStart injection, and hard-limit validation. | Longitudinal usefulness needs several weeks of real operation. |
| External practice radar | Contract complete | Targeted trigger policy and primary-source preference. | Search quality depends on the runtime model and web access. |
| Scheduling | Rendered/configured, smoke test required | Codex/Claude task instructions plus launchd/systemd/Windows renderers. | Native client scheduling cannot be declared active until visible and manually tested. |
| Git synchronization | Implemented | Installation commit/push path, effective author-identity preflight with repository-local overrides, scheduler-file staging, and non-fatal pending-push recovery. | Remote auth and company Git policy are environment-specific. |

## Release decision

The package is suitable for installation trials as a library-grade Skill. The current suite contains 42 passing standard-library tests covering installation, self-contained deployed runtime prompts, privacy, precomputed hook memory injection, Codex pagination/fallback, Claude discovery (including activity in the middle of large JSONL files), source-disable semantics, automatic repository discovery, unborn Git repositories, collection-time snapshot labeling, schedulers, and journal validation. Native Codex Automation, Claude Desktop scheduling, provider transcript access, and company Git push remain explicit environment verification gates rather than claimed completed evidence.
