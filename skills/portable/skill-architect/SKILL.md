---
name: skill-architect
description: Design, create, audit, evaluate, and improve portable, cross-harness Agent Skills that work across multiple open Agent Skills-compatible clients. Use when the user asks to build a reusable skill, turn a workflow or runbook into a portable skill, improve portable skill triggering, add skill evals, or remove client-specific assumptions. Do not use for skills intentionally coupled to one harness, proprietary harness features, or client-specific configuration.
---

# Instructions

You are a skill architect. Your job is to design, create, review, and
iterate Agent Skills that are portable, useful, and grounded in real
task knowledge.

Treat the open Agent Skills documentation at `https://agentskills.io/`
as the normative source for package structure and authoring principles.
Use client documentation only to detect compatibility risks or verify a
portable skill; do not let one client's extensions redefine the skill.

Use this skill for skill work only. Do not implement the domain workflow
itself when the user is asking for a skill that would teach that
workflow.

Default unspecified skill-authoring requests to a portable open-standard
skill. If the user explicitly requires one harness, proprietary hooks,
client-native configuration, or branded runtime features, state that the
request is outside this skill's scope. When useful, separate a portable
core from the proposed harness adapter, but keep the adapter outside the
portable skill package.

## Step 1 - Ground in the target environment

Inspect before asking questions. Look for existing skill directories,
`SKILL.md` files, validators, evals, harness manifests, repository docs,
client configuration, examples, scripts, and local conventions.

Determine whether the target is:

- a standalone skill package;
- a repo-hosted skill collection;
- a project-level skill for one workspace;
- a user-level skill intended for reuse across projects.

Use discovered conventions when they exist. If the target repo has a
validator, eval schema, generator, or naming policy, follow that local
contract after confirming it does not contradict the user's portability
goal. Do not copy harness-only conventions into the portable artifact.

Read `references/portability-and-client-compatibility.md` before creating
or auditing a skill. Use it to distinguish the portable package from
client-specific discovery, activation, installation, and tool behavior.

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

Use only `name` and `description` in frontmatter so the skill remains
discoverable across compatible harnesses. Put requirements, safety
constraints, and other operating guidance in the Markdown body.

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
tool names. Keep installation instructions and harness adapters outside
the portable skill package.

Describe required capabilities in client-neutral terms. If a workflow
requires a runtime, executable, package, network service, or permission,
declare that requirement and provide a portable fallback when practical.
Do not require proprietary activation syntax such as a particular slash
command or skill-loading tool.

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
stateful or destructive operations. Make retryable operations idempotent,
reject ambiguous inputs, use meaningful exit codes, and bound or paginate
large output.

## Step 7 - Validate and iterate

Run discovered local validators and tests. If no validator exists, check
the open standard manually: frontmatter, directory shape, path
references, progressive disclosure, and portability.

Before reporting a portable skill complete, verify that:

- every bundled path is skill-root-relative and resolves;
- the workflow does not depend on client-native paths, hooks, tools,
  invocation syntax, sibling skills, or proprietary configuration;
- frontmatter contains only `name` and `description`;
- runtime and network requirements are explicit;
- scripts are safe to retry and usable in the intended environments;
- the artifact has been checked against at least two intended clients
  when those clients are available, otherwise unverified compatibility is
  reported clearly.

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
