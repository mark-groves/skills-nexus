# Common Agent Skills format

Use this reference to check the shared `SKILL.md` package shape. The upstream
specification is at https://agentskills.io/specification.

## Interoperability floor

A skill is a directory containing `SKILL.md`. It may bundle runtime resources
such as `scripts/`, `references/`, and `assets/`. `SKILL.md` contains YAML
frontmatter followed by Markdown instructions.

The format is an interoperability floor, not a complete repository
architecture. It does not prescribe where maintainers store evals, observations,
release evidence, or harness adapters. It also does not make discovery paths,
activation, permissions, tools, or resource loading identical across clients.

## Frontmatter layers

The common required fields are:

- `name`: 1–64 lowercase ASCII letters, digits, and hyphens; match the package
  directory name.
- `description`: 1–1024 characters describing what the skill does and when it
  should activate.

The upstream format also defines optional fields such as `license`,
`compatibility`, `metadata`, and experimental `allowed-tools`. Support and
semantics can vary by client. Their existence in the format does not make them
the right canonical source of truth for every collection.

When a repository defines a smaller metadata contract, follow it. Skills Nexus
uses exactly `name` and `description` in canonical packages. Store licensing in
a bundled license when needed, requirements and safety constraints in operating
instructions, tested compatibility in repository evidence, and permissions or
presentation in target integrations.

## Runtime content

Write the body as instructions an agent can operate:

- task classification and inputs;
- step-by-step workflow;
- meaningful defaults and safety stops;
- examples only where they resolve ambiguity;
- observable validation before completion.

Add only knowledge the agent is likely to lack or mishandle. Keep the main body
under roughly 500 lines and move conditional detail to directly linked files.

Use:

- `scripts/` for deterministic executable operations;
- `references/` for schemas, policies, API detail, variants, and long examples;
- `assets/` for templates, images, boilerplate, and files used in outputs.

Reference files relative to the skill root and keep reference chains shallow.
Do not hard-code an installation root or depend on sibling skills.

## Validation

Run the target repository's validator first. When useful, also run the upstream
reference validator. Check:

- `SKILL.md` and valid YAML frontmatter exist;
- required fields are within limits and the name matches the directory;
- canonical fields obey the repository's stricter allowlist;
- linked resources exist and are necessary at runtime;
- packaging excludes eval answers, observations, and development artifacts;
- compatibility claims are backed by target-specific tests.

Passing a format validator proves package shape, not behavioral quality or
cross-client compatibility.
