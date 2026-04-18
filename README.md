# skills-nexus

Portable, reusable agent skills aligned with the
[open Agent Skill standard](https://agentskills.io/home), with a
simple repository contract:

- each skill lives in `skills/<name>/`
- a directory is a valid skill when it contains `SKILL.md`
- deployment is explicit through `scripts/deploy-skills.sh`
- validation is offline through `scripts/check-skills.sh`

## Quick Start

Use `--harness <name>` to select `harnesses/<name>.json`.

Deploy one skill:

```bash
bash scripts/deploy-skills.sh --harness codex --skill pr --scope user
```

Deploy multiple skills:

```bash
bash scripts/deploy-skills.sh --harness agents --skill commit --skill pr --scope user
```

Deploy all skills:

```bash
bash scripts/deploy-skills.sh --harness cursor --all --mode copy
```

Validate the repository:

```bash
bash scripts/check-skills.sh
```

## Repository Layout

```text
skills/      Canonical skill artifacts
harnesses/   Install roots for supported clients
scripts/     Deploy and validation entrypoints
tests/       Validator coverage
```

Supported harness manifests:

- `agents`
- `claude-code`
- `codex`
- `cursor`
- `kiro`

## Skill Contract

- `skills/<name>/` is the canonical portable artifact.
- Canonical `SKILL.md` frontmatter stays within the repo's supported subset: `name`, `description`, and optional `license`, `compatibility`, or `metadata`.
- Skill-local support files may live under `scripts/`, `references/`, `assets/`, and `evals/`.
- Harness manifests stay thin and define install roots only.

## Deployment Notes

`--skill` is the primary deployment path. `--all` is only a convenience flag for installing every immediate child of `skills/` that contains `SKILL.md`.

`symlink` is the default mode so edits in this repository show up immediately in installed skills. Use `--mode copy` when a client does not reliably discover symlinked skills.

Use `--dry-run` to inspect the install actions before making changes.

For project-scoped installs, pass `--scope project --project-root /path/to/project`.

## Validation

`scripts/check-skills.sh` runs the repository validator in offline, deterministic mode. It checks the skill directory contract, supported frontmatter, portability rules, thin harness manifests, deployment behavior, and repository-specific generated-content workflows.
