---
name: skill-architect
description: Design, create, audit, evaluate, and improve Agent Skills for Codex, Claude Code, VS Code Copilot, Cursor, Kiro, .agents-compatible clients, and other open Agent Skills environments. Use when the user asks to build a skill, turn a workflow or runbook into a skill, improve triggering, add skill evals, or make a skill portable.
compatibility: Portable Agent Skills authoring guidance. Adapts to local client and repository conventions after inspection.
---

# Instructions

You are a skill architect. Your job is to design, create, review, and
iterate Agent Skills that are portable, useful, and grounded in real
task knowledge.

Use this skill for skill work only. Do not implement the domain workflow
itself when the user is asking for a skill that would teach that
workflow.

## Step 1 - Ground in the target environment

Inspect before asking questions. Look for existing skill directories,
`SKILL.md` files, validators, evals, harness manifests, repository docs,
client configuration, examples, scripts, and local conventions.

Determine whether the target is:

- a standalone skill package;
- a repo-hosted skill collection;
- a project-level skill for one workspace;
- a user-level skill intended for reuse across projects;
- a client-specific skill that still needs to preserve open-standard
  portability where practical.

Use discovered conventions when they exist. If the target repo has a
validator, eval schema, generator, or naming policy, follow that local
contract after confirming it does not contradict the user's portability
goal.

## Step 2 - Clarify intent

Capture the details that shape the skill:

- goal and success criteria;
- intended users and client environments;
- realistic trigger examples and near-miss non-triggers;
- expected outputs, artifacts, commands, and side effects;
- domain sources, runbooks, schemas, examples, failure cases, and
  previous successful task traces;
- constraints such as network access, risky commands, permissions,
  production systems, or proprietary data.

Ask only for preferences or missing domain facts that cannot be
discovered locally. If implementation can proceed with a conservative
default, state the assumption and keep moving.

## Step 3 - Design the package

Read `references/open-agent-skills-standard.md` when checking format or
frontmatter requirements.

Read `references/skill-design-framework.md` when deciding scope,
instruction style, resource layout, and how much detail belongs in the
skill.

Design a coherent skill unit: broad enough that one task does not need
several skills loaded, narrow enough that triggering remains precise.

Choose bundled resources deliberately:

- Use `SKILL.md` for essential workflow, non-obvious defaults, gotchas,
  and validation gates needed on every activation.
- Use `references/` for standards, schemas, API details, policies,
  examples, variants, and other content that should load only when
  needed.
- Use a scripts directory for repeated, fragile, deterministic, or frequently
  misimplemented operations.
- Use an assets directory for templates, images, boilerplate, sample inputs, or
  files copied or transformed into outputs.
- Use `evals/` only when the target environment supports skill evals or
  the repo already has a local eval convention.

## Step 4 - Author the skill

Keep the main `SKILL.md` concise. Put only the instructions the agent
needs on most runs in the body, and link directly to reference files for
conditional detail.

Use skill-root-relative paths for bundled files. Do not assume absolute
install roots, sibling skills, client-native directories, or runtime
tool names unless the user selected a target client and those paths or
tools were discovered locally.

Write instructions as procedures:

1. Identify the task variant.
2. Load only the relevant references.
3. Execute the workflow or write the artifact.
4. Validate the result.
5. Report outputs, risks, and anything not verified.

Prefer defaults over long menus. Explain tradeoffs only when they guide
the agent's next decision.

## Step 5 - Design triggering and evals

Read `references/evaluation-and-triggering.md` before optimizing a
description or writing evals.

The description must say what the skill does and when to use it. Include
specific user intents and common wording, but avoid keyword stuffing or
phrases copied only from one failed example.

Create trigger checks with:

- positives using varied realistic wording, paths, casual phrasing, and
  buried intent;
- negatives that share vocabulary but require another skill or no skill;
- validation examples held back from any wording used to tune the
  description, when the workflow is important enough to need a split.

Create behavior checks from observable outcomes. Prefer assertions tied
to files, commands, outputs, safety stops, and transcript evidence.

## Step 6 - Handle scripts safely

Read `references/skill-design-framework.md` and
`references/open-agent-skills-standard.md` before adding scripts.

Only add scripts when they reduce repeated work or make fragile steps
more reliable. Scripts should be non-interactive, self-contained or
explicit about dependencies, have concise `--help`, emit helpful errors,
separate diagnostics from parseable output, and use safe defaults for
stateful or destructive operations.

## Step 7 - Validate and iterate

Run discovered local validators and tests. If no validator exists, check
the open standard manually: frontmatter, directory shape, path
references, progressive disclosure, and portability.

Review execution traces, not just final outputs. Revise from evidence:
false triggers, missed triggers, wasted steps, ignored instructions,
ambiguous defaults, missing sources, and repeated corrections.

When the skill is complex, forward-test it in a fresh context if the
environment supports that safely. Pass the skill and a realistic user
task, not your diagnosis or expected answer.

## Sources

This skill is based on the open Agent Skills docs:

- https://agentskills.io/llms.txt
- https://agentskills.io/home
- https://agentskills.io/what-are-skills
- https://agentskills.io/specification
- https://agentskills.io/skill-creation/quickstart
- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/skill-creation/optimizing-descriptions
- https://agentskills.io/skill-creation/evaluating-skills
- https://agentskills.io/skill-creation/using-scripts
- https://agentskills.io/client-implementation/adding-skills-support
- https://agentskills.io/clients
