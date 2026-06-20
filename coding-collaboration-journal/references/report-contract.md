# Report Contract

## Paths

Default daily path:

```text
journal/YYYY/MM/YYYY-MM-DD/report.md
journal/YYYY/MM/YYYY-MM-DD/evidence.json
journal/YYYY/MM/YYYY-MM-DD/run.json
```

Use numeric months (`01`, not `M1`) for natural sorting.

## Frontmatter

```yaml
---
date: 2026-06-19
timezone: Asia/Shanghai
status: active
coverage: partial
confidence: medium
privacy: Low
schema_version: 1
collector_version: installed-runtime
analysis_prompt_version: 1
rubric_version: collaboration-v1
models:
  - provider: openai
    model: gpt-x
  - provider: anthropic
    model: claude-x
sources:
  codex: complete
  claude: partial
---
```

## Required Sections

### `今日结论` / Executive Summary

One concise paragraph: what materially moved, what is verified, and the largest uncertainty.

### `工作与结果` / Work and Outcomes

Group by task, not by transcript. For each task:

- intended outcome;
- actual result;
- verification;
- remaining work;
- evidence IDs;
- linked repositories, sessions, and resources.

### `关键决策` / Decisions

Record choices, rationale, alternatives rejected, and who made the decision. Omit when there were no consequential decisions.

### `上下文索引` / Context Index

Index:

- sessions/threads and relevant turns;
- repositories, branches, commits, and working-tree state;
- external resources and local documents;
- prior reports used for continuity.

This section is always present, even if empty.

### `协作分析` / Collaboration Analysis

Always present. Explain the actual division of labor and interaction pattern:

- problem framing;
- context provision;
- decomposition and delegation;
- exploration vs implementation;
- correction and decision-making;
- verification and acceptance;
- knowledge externalization.

Support consequential claims with evidence.

### `做得好的地方` / Done Well

Optional. Include only specific, repeatable behavior with evidence and why it helped.

### `值得改进` / Could Improve

Optional. Include only actionable, evidence-supported changes. Avoid generic advice such as “communicate more clearly”.

### `综合评价` / Evaluation

Always present. It may be explicitly non-assessable:

> There is enough evidence to assess the implementation process, but not the production outcome; therefore the evaluation is limited to local execution and verification quality.

Use per-dimension labels rather than a single score:

```text
not-assessable | weak | mixed | strong
```

### `连续性` / Continuity

List:

- work inherited from prior days;
- open loops;
- next recovery context;
- active experiments affected today.

### `数据质量` / Data Quality

Always state:

- complete and failed sources;
- redaction level;
- missing evidence;
- coverage/confidence;
- collector anomalies.

## Evidence Citation Style

Use readable references such as:

```markdown
The acceptance criteria were added only after implementation had begun, followed by two direction changes. [E-CODEX-0042] [E-GIT-0081]
```

Every cited ID must resolve in `evidence.json`. A validator should reject dangling IDs.

## Structured Analysis Result

Prefer generating a machine-readable intermediate result:

```json
{
  "tasks": [],
  "decisions": [],
  "collaboration_analysis": [],
  "done_well": [],
  "could_improve": [],
  "evaluation": {
    "problem_framing": {"label": "mixed", "evidence": []}
  },
  "continuity": {},
  "data_quality": {}
}
```

Render Markdown from this structure to reduce format drift.

## Weekly Review

Weekly reviews live under `reviews/weekly/YYYY-Www.md` and should:

- consolidate repeated patterns and counter-evidence;
- review active experiments;
- compare similar task classes;
- select at most three high-leverage improvements;
- run targeted external-practice research only when triggered;
- update memory and pattern state.

## Monthly Review

Monthly reviews live under `reviews/monthly/YYYY-MM.md` and should:

- separate user improvement from model/tool/evaluator changes;
- compare like-for-like tasks and confidence bands;
- identify durable workflow improvements;
- close, continue, or revise experiments;
- propose changes to `AGENTS.md`, `CLAUDE.md`, skills, or automation with evidence;
- record what cannot yet be concluded.
