# External Practice Radar

## Purpose

Use external evidence to challenge local habits and discover better workflows, without turning every daily reflection into trend-chasing.

## Trigger Conditions

Research only when at least one is true:

- the same friction appears at least three times in 14 days;
- a new task class has no local baseline;
- an active experiment needs candidate interventions;
- a tool/model/client update may materially change the workflow;
- a local approach has repeatedly failed verification;
- the user explicitly asks for current best practices.

Daily reports may create a research candidate. Weekly review normally executes the research.

## Query Abstraction

Do not leak private names unnecessarily. Translate the local issue into a general technical/workflow question.

```text
Local:
payments-service callback worker keeps being changed incorrectly after long Codex sessions

Research query:
evidence-based workflow for AI coding agents modifying idempotent event consumers,
including task briefing, verification, and rollback practices
```

At Low privacy, private details remain in the journal's local comparison, but external search queries should still use only the specificity needed to find good evidence.

## Source Priority

1. official product documentation and changelogs;
2. standards and primary research;
3. maintainers' engineering guides and incident reports;
4. reproducible public repositories and benchmarks;
5. high-quality practitioner reports;
6. community discussion as weak signal.

Use current sources, record publication/access dates, and distinguish a product vendor's recommendation from independent evidence.

## Output Contract

Write a practice card under `radar/practices/`:

```yaml
id: RP-2026-014
local_pattern: P-007
question: How should acceptance criteria be established for agentic bug-fix work?
current_method: Free-form first prompt, criteria refined during implementation.
candidate_method: Structured task brief before edits.
mechanism: Reduces hidden assumptions and late direction changes.
source_quality: mixed
applicability:
  fits: Multi-file bug fixes with clear observable outcomes.
  does_not_fit: Open-ended research where criteria must emerge.
experiment: E-004
sources:
  - title: ...
    publisher: ...
    date: ...
    accessed: ...
    url: ...
```

The prose comparison should state:

- current local method;
- candidate alternative;
- supporting evidence and limitations;
- fit/non-fit conditions;
- proposed experiment.

Never say “industry best practice” without defining whose evidence and under what conditions.

## Tool Update Radar

Once per week, inspect official changelogs for enabled tools. A new feature is not automatically an improvement. Ask:

- Does it remove an observed friction?
- Does it change collection interfaces or retention?
- Does it alter evaluator comparability?
- Does it require migration or permissions?
- Can it be tested in a bounded experiment?

Record model/client changes in the next report epoch.
