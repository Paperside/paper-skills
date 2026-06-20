# Monthly Automation Prompt

Operate this installed journal repository in **monthly** mode. Treat the repository as the self-contained runtime: use `.journal/config.toml`, `AGENTS.md`, `docs/method/*`, `scripts/*`, memory, schemas, rubrics, and templates as the authoritative instructions. The original Skill is only needed for installation, upgrades, repair, or workflow evolution.

1. Read the completed local month, weekly reviews, active and closed experiments, pattern history, model/tool/skill/rubric epochs, and data-quality gaps.
2. Assess growth only from comparable task classes and sufficiently supported trends. Separate likely user improvement from model, client, repository, task-mix, and evaluator changes.
3. Identify durable workflow gains, persistent friction, rejected assumptions, and unresolved uncertainty.
4. Close, continue, or redesign experiments. Prefer one or two concrete next experiments over a long advice list.
5. Propose evidence-backed changes to `AGENTS.md`, `CLAUDE.md`, templates, hooks, automation, or this journal's rubric. Apply them only under the configured autonomy policy and always leave a reversible Git diff.
6. Update `reviews/monthly/YYYY-MM.md`, goals, bounded memory, and epoch records.
7. Validate, commit with `journal: YYYY-MM monthly review`, and push according to policy.

State explicitly what cannot be concluded from the available evidence.
