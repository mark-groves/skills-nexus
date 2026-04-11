# Migration Plan

## Goal

Move reusable skills out of `claude-crucible` and make this repository
the neutral home for skills that can be deployed into multiple agent
harnesses.

## What Moves Here

- Reusable skills and their bundled scripts/references/assets
- Skill inventory and portability metadata
- Harness deployment adapters

## What Stays In Harness Repos

- Agents/subagents
- Hooks and policy enforcement
- Harness-specific rules
- Harness bootstrap/install logic unrelated to skills

## Migration Sequence

1. Copy existing reusable skills into `skills/`.
2. Audit each skill for hardcoded install roots, repository-relative
   paths, and brand-specific wording.
3. Patch those assumptions so each skill can run when installed at
   `user` or `project` scope.
4. Introduce harness adapter manifests that define install roots.
5. Use one deploy script to install the canonical skill folders into the
   selected harness.
6. Only after deployment is stable, consider adding richer per-skill
   metadata or adapter overlays.

## Current Portability Findings

- `commit`: portable as-is
- `pr`: portable as-is
- `cloud-diagram`: now uses skill-root-relative bundled references only
- `drawio-shapes`: now uses bundled scripts, a skill-local `working/`
  directory, and same-tree sibling updates for `cloud-diagram`

## Recommended Conventions Going Forward

- Canonical skill ID matches the folder name.
- Every skill remains self-contained in its own directory.
- Bundled files are referenced relative to the installed skill
  directory, not the source repository.
- Skills follow the Agent Skills Open boundary: no runtime probing of
  user-level or project-level install roots.
- Harness adapters should only answer:
  - where a skill is installed
  - whether it installs as a directory
  - whether the harness needs a future overlay

## Suggested Phase 2

- Add `skill.json` per skill if you need:
  - tags
  - owner
  - maturity
  - compatible harness list
  - overlay requirements
- Keep `scripts/check-skills.sh` enforcing the no-discovery rule before
  deployment
