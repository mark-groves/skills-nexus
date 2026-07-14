# Portability And Client Compatibility

Use this reference when a skill must work across multiple clients or
installation scopes. Source docs:
https://agentskills.io/client-implementation/adding-skills-support,
https://agentskills.io/skill-creation/quickstart, and
https://agentskills.io/clients.

## Portability Goal

The Agent Skills format defines what goes inside a skill directory, not
one mandatory install location. A portable skill should be a normal file
tree that can be copied, symlinked, packaged, or installed by any
compatible client.

Keep the skill itself independent of where it is installed. Use
skill-root-relative references for bundled files and inspect the target
environment when client-specific behavior matters.

The specification standardizes the package, not every client behavior.
Clients can differ in discovery paths, activation, resource access,
permissions, supported runtimes, and optional frontmatter handling. A
conforming package is therefore necessary but not sufficient for
cross-client portability.

## Discovery Scopes

Compatible clients commonly support more than one scope:

- project-level skills for one workspace;
- user-level skills reused across projects;
- organization or bundled skills supplied by a platform;
- client-native directories;
- a cross-client dot-agents skills convention.

Do not hard-code these paths into portable skill instructions. Discover
the local convention only when installing or testing the skill, and keep
installation guidance outside the portable package.

## Activation Models

Clients may activate skills through:

- model-driven selection from a catalog of names and descriptions;
- explicit user mention, slash command, or skill picker;
- a dedicated activation or resource-loading tool.

Write descriptions for model-driven selection even when the target client
also supports explicit activation. The description remains the common
metadata surface across clients. Do not require a slash command, mention
syntax, picker, or dedicated loading tool for the workflow to make sense.

## Resource Loading

Clients may let the agent read files directly or may inject skill
content through a tool. Either way, shallow and explicit references make
skills easier to use:

- mention each relevant support file from `SKILL.md`;
- say when to load it;
- avoid reference files that require deep chains of further references;
- keep large generated assets out of context unless needed.

## Permissions

Some clients honor tool allowlists, some ask the user at runtime, and
some sandbox tool access. Treat frontmatter tool hints as one layer of
safety, not as a replacement for safe instructions.

If the skill needs risky commands, state the risk, require dry runs or
approval when appropriate, and design scripts with explicit confirmation
flags.

## Frontmatter And Runtime Requirements

Use `name` and `description` as the portable minimum. The open standard
also permits `license`, `compatibility`, `metadata`, and experimental
`allowed-tools`, but clients may interpret optional fields differently.
Add them only for real information and do not make core behavior depend
on them being enforced.

Express requirements as capabilities or dependencies rather than branded
tool names. Declare required executables, packages, network access, and
permissions. Prefer scripts with broadly available runtimes or document a
fallback when the intended client environments differ.

## Cross-Harness Boundary

Keep harness-only behavior outside the portable artifact. Examples
include proprietary hooks, native configuration, branded tool names,
client-specific activation syntax, and fixed install roots.

If a task combines portable and harness-specific concerns:

- create or improve the portable skill as one self-contained package;
- identify the harness adapter separately without placing it in the
  portable skill directory;
- report which compatibility claims were tested and which remain a static
  assessment;
- hand off work whose value depends entirely on one harness.

Do not call a client-optimized or dual-mode artifact portable merely
because its frontmatter conforms to the open specification.
