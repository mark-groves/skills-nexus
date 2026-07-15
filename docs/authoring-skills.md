# Authoring skills

Canonical runtime skills live under `skills/<name>/`. Each directory is a
self-contained package that can be copied, symlinked, or installed by a
compatible agent client.

Skills Nexus follows the common Agent Skills package shape and authoring
principles, but its canonical metadata contract is intentionally smaller than
the complete upstream specification. Format compliance is an interoperability
baseline; cross-client compatibility is a tested claim.

## SKILL.md

Use exactly `name` and `description` in canonical frontmatter:

```yaml
---
name: example-skill
description: Perform a specific workflow. Use when the user asks for that workflow or its common variants.
---
```

The `name` must match the directory and contain 1–64 lowercase letters, digits,
or hyphens. It cannot begin or end with a hyphen or contain consecutive
hyphens.

The `description` must be non-empty and no longer than 1024 characters. State
both what the skill does and when it should activate; this is the common
discovery surface across supported clients.

Do not add `license`, `compatibility`, `metadata`, `allowed-tools`, invocation
policy, or other client extensions to canonical frontmatter. Use a bundled
license file for skill-specific terms, put requirements and safety constraints
in the operating instructions, record tested compatibility in repository
documentation, and place client-native metadata in a target integration.

Write the Markdown body as an operating guide for the agent. Include the
workflow, important defaults, safety stops, and validation needed on most runs.
Keep background and conditional detail in focused reference files.

## Runtime resources

A skill may bundle resources used at runtime:

- `scripts/` for deterministic or frequently repeated operations
- `references/` for detailed material loaded only when needed
- `assets/` for templates and files used to produce outputs
- other domain-specific runtime files when the instructions use them directly

Use paths relative to the skill directory. Link support files directly from
`SKILL.md` and say when an agent should read or run each one. Shared skills
should express required capabilities without relying on a harness's tool names,
activation syntax, configuration, or fixed install path.

Evaluation definitions, expected outcomes, fixtures, observations, development
notes, and generated working files are not runtime resources. Store evaluation
material under `evals/<name>/` and raw observations under the gitignored
`.skill-feedback/` tree.

## Add and validate a skill

1. Create `skills/<name>/SKILL.md` with the minimal metadata contract.
2. Add only resources used by the runtime workflow.
3. Create `evals/<name>/evals.json` with trigger and behavior evidence.
4. Add focused fixtures under `evals/<name>/fixtures/` when needed.
5. Run the repository checks.

```bash
bash scripts/check-skills.sh
```

The validator checks naming, the minimal frontmatter contract, local links,
path portability, evaluation schemas, runtime packaging, harness manifests, and
the generated cloud-shape workflow.

The bundled [`skill-architect`](../skills/skill-architect/SKILL.md) provides a
deeper workflow for designing, auditing, evaluating, and iterating a reusable
skill.
