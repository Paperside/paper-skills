# Analysis Method

## What Is Being Evaluated

Evaluate the **collaboration process and observable outcomes**, not the developer's worth. The report should help the user decide what to repeat, change, or test.

## Evidence Hierarchy

From strongest to weakest:

1. external/user outcome, production observation, accepted review;
2. passing tests/build/lint and inspected Git state;
3. concrete repository changes and command results;
4. conversation decisions with traceable implementation;
5. agent or user claims without independent verification;
6. evaluator inference.

State the evidence level when it changes the conclusion.

## Daily Dimensions

Use `not-assessable`, `weak`, `mixed`, or `strong` with evidence and confidence.

### Problem Framing

- Was the intended outcome clear?
- Were constraints and definition of done known before implementation?
- Did the work solve the right problem?

### Context Organization

- Were relevant files, prior decisions, data, and constraints supplied efficiently?
- Did the user/agent repeatedly rediscover information?
- Was history retrieved when the task crossed days?

### Decomposition and Delegation

- Were tasks split into useful units?
- Was the agent given appropriate autonomy?
- Did parallel work create integration cost?

### Correction and Judgment

- Were wrong assumptions caught early?
- Did the user critically evaluate proposals?
- Did the agent surface uncertainty and alternatives?

### Verification Quality

- Were tests and other checks appropriate to risk?
- Was “implemented” confused with “verified”?
- Was acceptance based on observable evidence?

### Knowledge Externalization

- Were reusable decisions written into code, docs, tests, `AGENTS.md`, `CLAUDE.md`, a skill, or an experiment?
- Was repeated explanation reduced?

### Flow and Rework

- How many direction corrections, restarts, context reloads, or abandoned implementations occurred?
- Which were healthy exploration versus avoidable rework?

## Do Not Optimize Proxy Metrics

Prompt count, token count, lines changed, commits, and tool calls are diagnostic signals only. They are not goals. A complex investigation may legitimately use many turns; a one-line change may be low-value.

## Growth Analysis

Growth is a longitudinal inference. Require:

- comparable task classes;
- a sufficient sample;
- task difficulty/context notes;
- model, client, skill, rubric, and evaluator versions;
- both supporting and counter-evidence;
- confidence and alternative explanations.

Compare:

```text
bugfix ↔ bugfix
research ↔ research
refactor ↔ refactor
greenfield ↔ greenfield
incident response ↔ incident response
```

Avoid cross-category conclusions such as “faster than yesterday” when yesterday was a trivial fix and today was a distributed refactor.

## Evaluator Drift

Record an epoch whenever model/client/rubric/analysis prompt changes materially. For major changes:

1. select a small historical calibration set;
2. evaluate it with old and new evaluators when feasible;
3. note systematic label changes;
4. avoid splicing the trend line without a boundary marker.

## Pattern Thresholds

Default:

- `suspected`: one clear event or two weak signals;
- `confirmed`: three independent occurrences in 30 days, or one high-impact event with strong evidence;
- `improving`: intervention applied and recent comparable evidence is better;
- `resolved`: sustained improvement across the configured sample;
- `rejected`: counter-evidence outweighs the claim.

These are defaults, not laws. Explain deviations.

## Recommendation Quality Gate

A recommendation must include:

- observed problem;
- evidence IDs;
- expected mechanism;
- smallest practical intervention;
- applicability boundary;
- how to know whether it helped.

Bad:

> Give the AI more context.

Good:

> For cross-repository bug fixes, include the failing request, relevant service boundaries, and a definition of done in the first prompt. In three recent tasks, missing acceptance criteria led to late direction changes. Test this template for the next ten comparable bug fixes and track corrective turns before validation.
