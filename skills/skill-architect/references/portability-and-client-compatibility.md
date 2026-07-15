# Interoperability and client compatibility

Use this reference when a skill targets multiple clients, installation scopes,
or harness-specific capabilities. Source guidance:
https://agentskills.io/client-implementation/adding-skills-support and
https://agentskills.io/clients.

## Separate the layers

Use three explicit layers instead of treating “portable” as a property granted
by the file format:

1. **Runtime core** — `SKILL.md` and only the resources needed during a task.
2. **Repository evidence** — evals, observations, compatibility results, and
   promotion history.
3. **Target integration** — install destinations, permissions, hooks, UI
   metadata, plugins, and runtime-specific activation behavior.

A common runtime core can be copied, symlinked, packaged, or installed into
several clients. Cross-client compatibility remains a tested claim because
clients differ in discovery, activation, file access, permissions, tools,
context behavior, and supported runtimes.

## Discovery and activation

Clients may support project, user, organization, bundled, or client-native
skill scopes. Keep fixed install destinations in deployment adapters and user
documentation, not shared operating instructions.

Clients may activate through model selection from name and description,
explicit mention, a picker or command, or a resource-loading tool. Write a
description that works for model-driven selection. Do not make the workflow
depend on one client's activation syntax unless it is intentionally
target-specific.

## Resources, dependencies, and permissions

Use shallow skill-root-relative references so clients can read or inject the
same resources through different mechanisms. Load only what the current task
needs.

Express shared requirements as capabilities and dependencies. Declare required
executables, packages, network access, and permissions. Put safety stops in the
runtime instructions so they survive client differences. Give risky scripts
safe defaults, dry runs, and explicit confirmation where appropriate.

The common required metadata is `name` and `description`. Optional upstream
frontmatter can have uneven client support. Prefer a minimal canonical core and
put client-native permissions, hooks, or presentation metadata in the target
integration.

## Decide what to build

When a task mixes common and harness-specific behavior:

- keep a shared runtime core only when it remains useful on its own;
- add target integrations outside that core;
- make a fully target-specific artifact when proprietary behavior is the point;
- label each artifact honestly;
- report which client and scope combinations were executed and which remain
  unverified.

Do not add awkward fallbacks merely to preserve a portability label. Do not call
an artifact cross-client because its frontmatter parses in multiple clients.
