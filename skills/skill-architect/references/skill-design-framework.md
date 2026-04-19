# Skill Design Framework

Use this reference when deciding what a skill should contain and how it
should guide an agent. Source docs:
https://agentskills.io/skill-creation/best-practices and
https://agentskills.io/skill-creation/using-scripts.

## Start From Real Expertise

Ground the skill in real task evidence:

- completed task transcripts and corrections;
- internal docs, runbooks, style guides, and policies;
- API specs, schemas, configuration files, and contracts;
- review comments, issue discussions, and recurring failures;
- version control history, especially patches that fixed real problems;
- examples of desired inputs, outputs, and edge cases.

Avoid skills made from generic domain summaries. A useful skill captures
the procedures, defaults, tools, and failure modes that an agent would
not reliably infer on its own.

## Scope The Skill

A skill should cover one coherent unit of work. Scope it like a durable
workflow, not like a single command and not like an entire department.

Good scope signs:

- one user intent activates it naturally;
- the workflow has common inputs and outputs;
- the same references, scripts, or assets are reused across tasks;
- the skill can state clear success criteria.

Scope is too narrow when a normal task would need several skills loaded.
Scope is too broad when the description must list many unrelated intents
or when most instructions do not apply on a given run.

## Spend Context Carefully

Every line in `SKILL.md` competes with the user's request, system
instructions, and other active skills. Add what the agent would likely
miss. Cut what a capable general model already knows.

Prefer:

- exact tool choices over generic "use best practices";
- concrete edge cases over broad caution;
- local conventions over universal explanations;
- one short example over several paragraphs of prose.

## Calibrate Control

Use high-level guidance when many approaches are valid. Explain the
reason behind a constraint when context-sensitive judgment matters.

Use prescriptive steps when order, safety, or consistency is fragile.
For risky workflows, specify stop conditions, required checks, dry runs,
and approval points.

Provide defaults rather than menus. Mention alternatives only when the
agent needs a fallback rule.

## Write Procedures

Effective skill bodies usually follow this shape:

1. Classify the task variant.
2. Load only the relevant references.
3. Gather required facts and ask only for missing intent.
4. Execute the workflow.
5. Validate the output.
6. Report the result and any unverified assumptions.

Use gotchas for non-obvious constraints. Use checklists when omissions
are common. Use templates when output format matters.

## Choose Resources

Keep `SKILL.md` for instructions needed on most activations.

Move details into `references/` when they are long, variant-specific,
or only needed conditionally. Each reference should be focused enough
that loading it is obviously worthwhile.

Use `assets/` for files consumed or copied by the workflow, not for
instructions the agent needs to read.

Add `scripts/` when the agent would otherwise rewrite the same fragile
logic repeatedly or when deterministic behavior matters.

## Script Design

Prefer an existing one-off package command when it is short, stable, and
easy to invoke. Pin versions where reproducibility matters. State runtime
requirements in the skill or compatibility field.

Bundle a script when command lines become hard to reproduce or when the
logic deserves tests. Scripts should:

- accept input via flags, environment variables, files, or stdin;
- avoid prompts and other interactive behavior;
- provide concise `--help` with examples;
- print actionable error messages;
- put parseable output on stdout and diagnostics on stderr;
- use structured output such as JSON, CSV, or TSV when another tool or
  agent will consume it;
- support dry runs for destructive or stateful operations;
- use safe defaults and explicit confirmation flags for risky actions;
- limit output size or provide pagination/output-file options.

## Iterate From Evidence

First drafts are rarely final. Run the skill on real tasks, inspect the
trace, and revise based on observed behavior:

- false positives or missed triggers;
- wasted discovery steps;
- instructions followed in the wrong variant;
- vague defaults that caused extra attempts;
- repeated user corrections;
- missing validation steps.

Do not patch every single failure with a narrow sentence. Look for the
general missing rule, default, source, or resource split that explains
the failure.
