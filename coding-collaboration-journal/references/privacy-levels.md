# Privacy Levels

Privacy level controls **what is persisted in evidence**, not merely how the final report is worded. Default and recommended level: `Low`.

The orchestrator may hold a credential-scrubbed provider payload transiently in memory to discover repository paths before applying Medium or High abstraction. It must apply the selected level before writing any durable source, evidence, cache, log, or report artifact.

## Always Excluded

Regardless of level, do not persist:

- passwords, passphrases, PINs;
- API keys, access tokens, refresh tokens, OAuth credentials;
- session cookies, authorization headers, bearer tokens;
- private SSH/PGP/TLS keys and seed phrases;
- database connection strings containing credentials;
- raw secret-manager values;
- one-time codes and recovery codes.

Do not remove ordinary technical words merely because a key name contains `token` or `secret`; inspect context. Record that a redaction happened without recording the secret.

## Low — Full Context (Recommended)

### Retain

- repository and project names;
- local paths and file names;
- prompts and agent messages;
- code snippets, diffs, commands, and tool outputs;
- internal architecture, issue/PR references, resources, and decisions;
- customer or business context when it is part of the user's authorized work record;
- full continuity across days.

### Redact

Only credentials/authentication secrets and clearly personal authentication material.

### Use When

The journal is stored in an authorized company/private personal repository and complete context is more valuable than broad portability.

## Medium — Business-Sensitive Aliasing

Includes Low's mandatory credential removal, plus alias or generalize:

- customer/user names and direct identifiers;
- internal hosts, IPs, environment URLs, account IDs, and tenant IDs;
- unreleased product codenames;
- sensitive business metrics, prices, contract values, or datasets;
- personal employee information;
- exact incident details that are not needed to preserve the technical lesson.

### Preserve

- technical causality;
- component relationships;
- task type and constraints;
- decision rationale;
- test and outcome semantics;
- stable aliases across days, e.g. `customer-A`, `service-auth`, `repo-3`.

The alias registry belongs in local journal state and follows the same repository access controls.

## High — Idea-Level Abstraction

Do not persist raw transcripts, raw tool output, full diffs, repository names, file names, internal URLs, issue IDs, or project identifiers.

Store only:

- generalized problem statement;
- constraints and reasoning pattern;
- architecture/algorithm ideas;
- abstracted decisions and tradeoffs;
- generalized collaboration behavior;
- sanitized outcome and learning.

Example:

```text
Low: Changed payments-service/src/callback/idempotency.ts after Codex found duplicate event consumption in PR #482.
High: Revised an event-consumer idempotency boundary after the agent identified duplicate processing in a backend service.
```

High privacy reduces continuity and auditability. The report must state this limitation.

## Redaction Pipeline

1. parse provider-native records without durably writing them;
2. remove always-excluded secret material;
3. discover transient routing context such as working directories when needed;
4. apply selected level to content and identifiers before persistence;
5. compute hashes on the persisted representation;
6. write evidence;
7. render report only from persisted evidence.

Never generate a detailed Low-level report and then delete the evidence it relied on.

## Deterministic Secret Boundary

The runtime applies credential redaction while capturing hooks, provider records, Git output, manual notes, and startup memory. Before commit, `validate_journal.py` scans all durable user-data surfaces, including provider-native `sources/*.json`, hook event JSONL, reports, reviews, memory, notes, state, and configuration. It detects common token formats, private-key blocks, authorization/cookie headers, URL credentials, JWTs, and labeled secret assignments.

This is a guardrail, not magic classification: unknown opaque credentials without a recognizable label or format can evade pattern matching. The analysis agent must still avoid persisting secrets, and users should keep secret files under excluded paths.

## User Overrides

Support explicit include/exclude rules:

```toml
[privacy]
level = "Low"
exclude_paths = ["**/.env", "**/secrets/**"]
exclude_repositories = []
include_repositories = []
custom_sensitive_terms = []
```

An override cannot re-enable credential storage.
