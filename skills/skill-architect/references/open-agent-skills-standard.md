# Open Agent Skills Standard

Use this reference when checking whether a skill package follows the open
Agent Skills format. Source docs: https://agentskills.io/specification,
https://agentskills.io/what-are-skills, and https://agentskills.io/home.

## Core Shape

A skill is a directory containing `SKILL.md`. The skill may also include
supporting directories such as `scripts/`, `references/`, and `assets/`.
Other files may exist when they directly support the skill.

`SKILL.md` contains YAML frontmatter followed by Markdown instructions.
Agents discover skills from frontmatter first, then load the body only
after activation.

## Frontmatter

Required fields:

- `name`: skill identifier. Use 1-64 characters, lowercase ASCII letters,
  digits, and hyphens. Do not start or end with a hyphen, do not use
  repeated hyphens, and keep it identical to the skill directory name.
- `description`: 1-1024 characters. State what the skill does and when
  to use it. This is the primary trigger surface.

Optional fields:

- `license`: short license name or a reference to a bundled license file.
- `compatibility`: 1-500 characters if present. Include only when the
  skill has real environment, client, package, network, or system
  requirements.
- `metadata`: string-to-string map for client or organization-specific
  properties. Use specific key names to avoid accidental conflicts.
- `allowed-tools`: experimental space-separated tool allowlist. Support
  varies by client, so treat it as an optimization rather than the only
  safety boundary.

## Body Content

There is no required Markdown structure. Write the body as operating
instructions for an agent:

- task classification;
- step-by-step workflow;
- examples of input and output when useful;
- common edge cases and safety stops;
- what to validate before reporting completion.

Keep generic background out of the body. Add only knowledge the agent is
likely to lack or mishandle without the skill.

## Optional Directories

Use `scripts/` for executable code. Scripts should be self-contained or
explicit about dependencies, non-interactive, documented with concise
`--help`, and safe to retry when possible.

Use `references/` for documentation that should load on demand: schemas,
API details, policy excerpts, standards, long examples, variants,
decision tables, and troubleshooting guides.

Use `assets/` for resources used in outputs: templates, images,
boilerplate, sample files, fonts, fixtures, or other files copied or
transformed by the workflow.

Avoid extra human-facing documentation files unless they directly help an
agent perform the task.

## Progressive Disclosure

Design for three levels of loading:

1. Metadata: `name` and `description` are visible before activation.
2. Instructions: the full `SKILL.md` body loads after activation.
3. Resources: bundled files load only when instructions point to them.

Keep `SKILL.md` under roughly 500 lines and 5000 tokens. Move detailed
material into directly linked files. Tell the agent when to read each
file instead of saying to browse the whole reference directory.

## File References

Reference bundled files with paths relative to the skill root. Keep
reference chains shallow: `SKILL.md` should directly mention the support
files an agent might need.

Do not rely on absolute install roots, sibling skills, or client-native
locations unless the target environment requires them and the skill is
explicitly not intended to be portable.

## Validation

When a local validator exists, run it. If not, manually check:

- `SKILL.md` exists and starts with valid YAML frontmatter;
- required fields are present and within limits;
- `name` matches the directory;
- optional fields are non-empty and shaped correctly;
- referenced files exist;
- large details are in references or assets instead of the main body;
- examples and commands are safe for the intended environment.
