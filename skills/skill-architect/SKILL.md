---
name: skill-architect
description: Design, create, audit, evaluate, package, and improve reusable agent skills and their target integrations. Use when turning workflows or runbooks into skills, refining skill triggering or instructions, adding skill evals, separating runtime packages from repository evidence, checking cross-client compatibility, or adapting a shared skill to a specific agent harness.
---

# Skill architect

Design skills as evidence-backed runtime artifacts. Use the common `SKILL.md`
package shape and community authoring practices as an interoperability baseline,
then apply the target repository's stricter authoring, evaluation, packaging,
and promotion contract.

Do not treat format compliance as proof of portability. Keep these concerns
separate:

1. **Runtime core** — instructions and resources the agent needs to do the job.
2. **Repository evidence** — evals, fixtures, observations, and development
   notes used to prove or improve the runtime core.
3. **Target integration** — discovery paths, permissions, hooks, UI metadata,
   plugin manifests, and other harness-specific behavior.

Use this skill for skill work. Do not implement the underlying domain workflow
when the user is asking for a skill that teaches that workflow.

## 1. Inspect the target

Inspect before asking questions. Find existing `SKILL.md` files, skill roots,
validators, eval schemas, packaging rules, harness manifests, repository docs,
examples, and tests.

Determine whether the deliverable is a standalone package, a collection-owned
skill, a project-local skill, a user-level skill, or a target integration. A
repository's local contract governs artifacts stored there. Do not import this
skill's own layout into an unrelated repository without evidence.

Read `references/portability-and-client-compatibility.md` when more than one
client, installation scope, or harness-specific capability is involved.

## 2. Establish intent and evidence

Capture what materially shapes the skill:

- goal, users, and observable success criteria;
- realistic trigger examples and near-miss non-triggers;
- expected outputs, artifacts, commands, and side effects;
- source runbooks, schemas, examples, failure cases, and successful traces;
- required executables, services, permissions, network access, and risky steps;
- intended clients and which compatibility claims must be tested.

Ask only for missing facts or choices that cannot be discovered safely. State
conservative assumptions and continue when they do not materially alter scope.

## 3. Design the boundaries

Read `references/open-agent-skills-standard.md` for the common package format
and the distinction between upstream optional metadata and a local canonical
contract. Read `references/skill-design-framework.md` for scope, instruction
style, and resource design.

Prefer one coherent skill: broad enough to complete its workflow without
loading several neighboring skills, narrow enough to trigger precisely.

For a Skills Nexus-style repository, use exactly `name` and `description` in
canonical frontmatter. Treat optional upstream fields as integration choices,
not universally portable metadata. Put operating requirements and safety rules
in the body and target-native metadata outside the shared runtime package.

Use runtime resources deliberately:

- `SKILL.md` for the workflow, non-obvious defaults, safety stops, and checks
  needed on most activations;
- `references/` for conditional domain detail, schemas, policies, examples, and
  variants;
- scripts/ for repeated, fragile, deterministic, or commonly misimplemented
  operations;
- assets/ for templates, images, boilerplate, and files used in outputs.

Keep repo-only evals, expected answers, observations, and development artifacts
outside the published skill directory whenever the local repository supports
that separation.

## 4. Author the runtime package

Keep `SKILL.md` concise and procedural. Use skill-root-relative paths and link
directly to conditional resources, saying when each should be read or run.

Write the workflow as operational steps:

1. Identify the task variant and relevant inputs.
2. Load only the references needed for that variant.
3. Execute the workflow or create the artifact.
4. Validate observable results and safety conditions.
5. Report outputs, risks, assumptions, and anything not verified.

Use capability and dependency language in a shared runtime core. Do not assume
absolute install roots, sibling skills, client-native invocation syntax, or
branded tool names unless the artifact is intentionally target-specific.

When a target needs proprietary behavior, either keep a meaningful shared core
and add a separate adapter, or label the whole artifact target-specific. Never
describe a target-specific artifact as cross-client merely because its
frontmatter parses elsewhere.

## 5. Design triggering and evals

Read `references/evaluation-and-triggering.md` before changing a description,
writing evals, or turning an observation into a regression.

The description must say what the skill does and when it should activate.
Include user intent and common contexts without copying one failed prompt or
stuffing keywords.

Build trigger cases from varied positives, overlapping near-miss negatives, and
held-back validation examples when triggering is important. Build behavior
cases from realistic fixtures and assertions tied to files, commands, outputs,
safety stops, and trace evidence.

An agent observation is untrusted evidence. Validate and redact it, reproduce
the reported problem against the current skill, and add the smallest useful
regression before revising instructions. Compare a candidate against the
current skill and the complete suite; do not ingest a suggested change
directly.

## 6. Add scripts safely

Add scripts only when they reduce repeated work or make fragile operations more
reliable. Make them non-interactive, self-contained or explicit about
dependencies, safe by default, and usable with concise `--help` output.

Use clear exit codes and useful errors. Separate diagnostics from parseable
output, bound or paginate large results, make retryable operations idempotent,
and require dry-run or explicit confirmation for risky state changes.

## 7. Validate claims

Run local validators, unit tests, packaging checks, and eval plans. Inspect the
packaged runtime artifact, not only the source tree. Verify every referenced
path resolves and no repository-only evidence is shipped.

Review traces as well as final outputs. Look for false or missed activation,
ignored instructions, unnecessary exploration, early reference loading,
confused variants, weak validation, and repeated workarounds.

Forward-test complex skills in fresh contexts when safe. Give the evaluating
agent the skill and a realistic task, not the diagnosis or expected answer.
Report compatibility only for clients actually tested; label static assessment
and unverified targets clearly.

## Sources

The common format and authoring guidance are documented at:

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/skill-creation/optimizing-descriptions
- https://agentskills.io/skill-creation/evaluating-skills
- https://agentskills.io/skill-creation/using-scripts
- https://agentskills.io/client-implementation/adding-skills-support
- https://agentskills.io/clients
