# Authoring skills

Skills in this repository follow the Agent Skills directory format and are
organized by portability:

- `skills/portable/<name>/` contains skills usable across compatible harnesses.
- `skills/harness/<harness>/<name>/` contains reusable skills tied to one
  supported harness.

Each skill directory contains a `SKILL.md`. The folder name is also its install
name and must be unique across portable and harness-specific collections.

## SKILL.md

Use only `name` and `description` in frontmatter for consistent discovery
across harnesses:

```yaml
---
name: example-skill
description: Perform a specific workflow. Use when the user asks for that workflow or its common variants.
---
```

The `name` must match the directory and contain 1–64 lowercase letters, digits,
or hyphens. It cannot begin or end with a hyphen or contain consecutive
hyphens.

The `description` must be non-empty and no longer than 1024 characters. Write
both what the skill does and when it should activate; this is the text a
harness sees before loading the full instructions.

Write the Markdown body as an operating guide for the agent. Include the
workflow, important defaults, safety stops, and validation needed on most runs.
Keep background and conditional detail in focused reference files.

## Supporting files

A skill can bundle resources that support its workflow:

- `scripts/` for deterministic or frequently repeated operations
- `references/` for detailed material loaded only when needed
- `assets/` for templates and files used to produce outputs
- `evals/` for this repository's trigger and behavior evaluation cases

Use paths relative to the skill directory. Link support files directly from
`SKILL.md` and say when an agent should read or run each one. Portable skills
should express required capabilities without relying on a harness's tool names,
activation syntax, configuration, or fixed install path.

## Add and validate a skill

1. Create the skill directory in the appropriate collection.
2. Add `SKILL.md` with the minimal frontmatter and workflow instructions.
3. Add only the supporting files used by that workflow.
4. Add evaluation cases when activation or behavior needs executable evidence.
5. Run the repository checks.

```bash
bash scripts/check-skills.sh
```

The validator checks naming, directory structure, frontmatter, local links,
portable path usage, evaluation schemas, deployment behavior, harness
manifests, and the generated cloud-shape workflow.

The bundled [`skill-architect`](../skills/portable/skill-architect/SKILL.md)
provides a deeper workflow for designing, auditing, and iterating a portable
skill.
