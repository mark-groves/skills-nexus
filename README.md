# skills-nexus

Portable, reusable agentic skills with harness-specific deployment.

## Purpose

`skills-nexus` is the source of truth for reusable skills that should
outlive any single agent harness. The repository keeps skills in one
place, tracks their portability status, and provides deployment scripts
that install them into a specific harness at either user or project
scope.

The current migration strategy is pragmatic:

- Keep each existing skill folder intact as the canonical source.
- Remove repo-specific and harness-specific path assumptions.
- Add thin harness adapters around the skill folders instead of
  duplicating the skills per harness.

## Repository Layout

```text
skills/
  <skill-name>/              # Canonical skill folders
templates/
  skill/
    claude-template/         # Starter template from the original harness
harnesses/
  claude-code.json           # Install roots and adapter metadata
  codex.json
catalog/
  skills.json                # Skill inventory and migration notes
docs/
  migration-plan.md          # Recommended migration sequence
scripts/
  deploy-skills.sh           # Install selected skills by harness/scope
```

## Current Position

- Source skills migrated from `claude-crucible`: `commit`, `pr`,
  `cloud-diagram`, `drawio-shapes`
- Initial harness adapters scaffolded for `claude-code` and `codex`
- Canonical skills use bundled files via skill-root-relative paths;
  harnesses own install discovery and precedence

## Deployment

The deploy script supports:

- `--harness <name>`: target harness adapter
- `--scope user|project`: install to user home or into a project
- `--mode symlink|copy`: symlink by default, copy when isolation matters
- `--skill <name>` or `--all`: select which skills to install

Examples:

```bash
./scripts/deploy-skills.sh --harness claude-code --scope user --all
./scripts/deploy-skills.sh --harness codex --scope user --skill commit --skill pr
./scripts/deploy-skills.sh --harness codex --scope project --project-root /path/to/project --all
./scripts/deploy-skills.sh --harness claude-code --scope user --all --dry-run
```

## Recommended Migration Model

1. Treat `skills/<name>/` as the canonical artifact.
2. Keep harness install rules in `harnesses/*.json`, not inside the
   skills themselves.
3. Put only reusable skill content here.
4. Leave harness-specific hooks, agents, and rules in each harness repo.
5. Convert genuinely harness-specific skills into adapters or forked
   variants only when the behavior cannot be shared.

## Portability Rule

Follow the Agent Skills Open convention:

- Skills reference bundled scripts, references, and assets relative to
  their own root.
- Skills do not probe user-level or project-level install locations at
  runtime.
- Harnesses and clients handle install discovery, scope precedence, and
  deployment layout.

## Maintenance

- Run `bash scripts/check-skills.sh` to catch install-discovery
  regressions in canonical skills.
- Add optional per-skill metadata files once adapter behavior diverges.
- Split any future harness-specific prompting into adapter overlays
  rather than mutating the canonical skill body.
