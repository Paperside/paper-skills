# Coding Collaboration Journal

An Agent Skill for installing and maintaining a long-running AI coding collaboration journal for Codex and Claude Code.

This is not a prompt for writing a daily summary. It is a local, Git-backed system that gathers conversations, repositories, code changes, tests, tool calls, and referenced resources; writes evidence-linked daily reflections; and maintains longer-term memory, patterns, and improvement experiments.

## What It Does

- Guides setup for the journal repository, data sources, timezone, daily run time, privacy level, Git remote, and scheduler.
- Installs a self-contained journal runtime with scripts, prompts, method docs, schemas, rubrics, templates, and memory scaffolding.
- Reads Codex and Claude Code activity through source adapters and normalizes both into one evidence format.
- Correlates local Git repositories, branches, commits, uncommitted work, test outcomes, documents, and web resources.
- Generates daily `report.md`, `evidence.json`, and `run.json` artifacts.
- Distinguishes `no-activity` from `incomplete-collection` instead of treating missing evidence as a quiet day.
- Maintains bounded memory for user preferences, project continuity, collaboration patterns, experiments, open loops, memory candidates, and an optional precomputed session briefing.
- Supports weekly and monthly reviews that compare similar work over time and propose evidence-backed workflow improvements.

## Design Principles

1. Evidence first: the model interprets evidence; it does not invent it.
2. Full context by default: the recommended privacy level keeps project details while always removing credentials and authentication material.
3. Separate facts from evaluation: consequential claims should point back to conversations, repositories, commits, files, tests, or resources.
4. Daily reports explain process; weekly and monthly reviews track change over time.
5. Automatic but interruptible: routine runs can be unattended, while workflow mutations remain proposal-gated by default.
6. One semantic core, multiple source adapters: Codex and Claude Code differ at the collection layer, not in the report model.

## Skill Layout

```text
coding-collaboration-journal/
├── SKILL.md                    # routing and execution constraints
├── agents/                     # UI-facing skill metadata
├── skill-ir/                   # platform-neutral semantic contract
├── references/                 # method docs, runtime contracts, adapters
├── scripts/                    # bootstrap, collectors, hooks, doctor, validation
├── assets/                     # generated journal prompts and scaffold files
├── evals/                      # trigger and output-contract checks
├── tests/                      # standard-library regression tests
└── reports/                    # validation and quality notes
```

Several design choices in this Skill were informed by [yaojingang/yao-meta-skill](https://github.com/yaojingang/yao-meta-skill), especially the separation between a compact `SKILL.md`, detailed references, reusable scripts, and explicit evaluation artifacts. Thank you to that project for making those patterns concrete.

## Installed Journal Runtime

After installation, the generated journal repository is intended to run routine daily, weekly, and monthly jobs from its own files:

```text
my-ai-journal/
├── .journal/config.toml
├── automation/
├── scripts/
├── docs/method/
├── schemas/
├── rubrics/
├── templates/
├── memory/
├── journal/
└── reviews/
```

The original Skill remains useful for installation, upgrade, repair, migration, and workflow evolution. Routine automation prompts treat the installed repository as the self-contained runtime.

## Language Templates

Installation supports lightweight template localization. `zh*` languages generate Chinese `README.md`, `AGENTS.md`, `CLAUDE.md`, report template, and automation prompts; `en*` languages generate English versions. Unsupported language tags keep the requested `journal.language` in config and fall back to English templates, so the scheduled agent can still write generated prose in the configured language.

Method docs under `docs/method/` remain the canonical English runtime contract.

## Memory System And Beta Session Injection

Daily runs maintain the memory system automatically:

- L0: dated reports and evidence packs;
- L1: `memory/candidates.yaml` for proposed memory changes;
- L2: operational memory files for preferences, projects, patterns, experiments, and open loops;
- L3: `memory/session-briefing.md`, a compact briefing regenerated during the daily run.

`SessionStart` injection is Beta and disabled by default. When enabled with `[memory] inject_on_session_start = true`, the hook reads only the precomputed `memory/session-briefing.md`, applies redaction again, and caps it before injection. It does not synthesize memory on demand during interactive work.

## Install As A Skill

Place the complete `coding-collaboration-journal/` directory in the Skill directory used by your agent environment. For Codex personal skills, this is typically:

```text
${CODEX_HOME:-~/.codex}/skills/coding-collaboration-journal/
```

Then ask Codex to use `$coding-collaboration-journal`, or describe the desired durable journal system in natural language.

## Local Validation

```bash
python3 scripts/validate_skill.py .
python3 -m unittest discover -s tests -v

python3 scripts/bootstrap.py \
  --output /tmp/my-ai-journal \
  --sources codex,claude \
  --privacy Low \
  --timezone Asia/Shanghai \
  --run-time 02:00 \
  --git-user-name "AI Collaboration Journal" \
  --git-user-email "journal@local.invalid" \
  --yes

python3 /tmp/my-ai-journal/scripts/doctor.py --root /tmp/my-ai-journal
python3 /tmp/my-ai-journal/scripts/validate_journal.py --root /tmp/my-ai-journal
```

## Defaults

- Sources: enable detected Codex and Claude Code sources.
- Privacy: `Low`, with mandatory credential and authentication-secret removal.
- Schedule: `02:00` local time, reporting the previous local calendar day.
- Scheduler: Codex Automation when available, with clear local-runtime conditions and a manual smoke test before marking it active.
- Language templates: Chinese for `zh*`, English for `en*` and unsupported tags.
- Git: automatic commit by default; push policy follows user configuration.
- External practice radar: targeted, not broad daily web research.
- Memory maintenance: automatic during daily runs.
- Session memory injection: disabled by default; Beta opt-in.

## Boundaries

The Skill can install, configure, validate, and repair the local journal system. Installation requires an explicit user-approved plan; `scripts/bootstrap.py` refuses non-dry-run installation without `--yes`. The Skill should never claim that hooks, schedulers, source readers, or remote Git push are active without a smoke test. When a client has no callable API for creating an automation, the Skill writes exact setup instructions and leaves the final UI confirmation to the user.
