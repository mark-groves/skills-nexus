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

## Discovery Scopes

Compatible clients commonly support more than one scope:

- project-level skills for one workspace;
- user-level skills reused across projects;
- organization or bundled skills supplied by a platform;
- client-native directories;
- a cross-client dot-agents skills convention.

Do not hard-code these paths into skill instructions unless the user is
building for one explicit client. Instead, discover the local convention
from repository files, client docs, or user-provided context.

## Activation Models

Clients may activate skills through:

- model-driven selection from a catalog of names and descriptions;
- explicit user mention, slash command, or skill picker;
- a dedicated activation or resource-loading tool.

Write descriptions for model-driven selection even when the target client
also supports explicit activation. The description remains the common
metadata surface across clients.

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

## Client-Specific Tradeoffs

When local client conventions conflict with portability, prefer the
user's target. Document the tradeoff in the skill or final response:

- portable open-standard skill;
- client-optimized skill with known non-portable assumptions;
- dual-mode skill that discovers local conventions and falls back to the
  open format.
