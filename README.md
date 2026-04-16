# skills-nexus

`skills-nexus` is the portable home for reusable agent skills. The stable contract is simple: each skill lives in `skills/<name>/`, canonical `SKILL.md` files follow the Agent Skills open specification, deployment is explicit, and repo validation is offline.

## Purpose

This repository keeps reusable skills in one place so they can be installed into multiple clients without changing the skill artifact itself. Skills are meant to evolve centrally from real usage, so symlinked installs are the default operating model and copied installs are the fallback when a client has discovery problems.

## Repo Contract

- `skills/<name>/` is the canonical portable artifact.
- An immediate child of `skills/` is a valid skill only if it contains `SKILL.md`.
- Canonical `SKILL.md` frontmatter stays within the open-spec subset used by this repo: `name`, `description`, and optional `license`, `compatibility`, or `metadata`.
- Skill-local support files may live under `scripts/`, `references/`, `assets/`, and `evals/`.
- Harness manifests stay thin and describe install roots only, with the harness id inferred from `harnesses/<name>.json`.
- Top-level helper scripts are limited to install/deploy and validation concerns.
- `README.md` is the single repo guide.
- What this repo is not: no harness-specific skill forks, no shared runtime content outside skill folders, no generic automation dumping ground.

## Install/Deploy Usage

`--skill` is the primary path. `--all` is a convenience flag that deploys every immediate child of `skills/` that contains `SKILL.md`.

```bash
bash scripts/deploy-skills.sh --harness agents --skill commit --scope user
bash scripts/deploy-skills.sh --harness codex --skill pr --scope project --project-root /path/to/project
bash scripts/deploy-skills.sh --harness cursor --all --mode copy --dry-run
```

Use `--harness <name>` to select `harnesses/<name>.json`. Supported harnesses are `agents`, `codex`, `claude-code`, `cursor`, and `kiro`. The deploy script stays neutral: it only installs the canonical skill artifact into the selected root. Default mode is `symlink` so edits made in this repo appear immediately in installed skills. Use `--mode copy` when a client or environment fails to discover symlinked skills reliably.

## Validation

Run the repo validator with:

```bash
bash scripts/check-skills.sh
```

It checks the skill directory contract, canonical frontmatter, repo-local eval structure, tracked generated junk, portability rules, backticked skill-local file references, thin harness manifests, deploy behavior, and the draw.io shape handoff workflow. The validator runs deterministically and offline.

## Maintainer Workflow For Shape-Catalog Refresh

1. Invoke the `drawio-shapes` skill to refresh the extracted draw.io data and produce provider-specific generated fragments.
2. Review the generated fragments before importing them anywhere else.
3. Invoke the `cloud-diagram` skill to validate and import those fragments into its bundled references.
4. Keep the generated fragments under review; the consumer skill owns mutation of its bundled references.
5. Rerun `bash scripts/check-skills.sh` to confirm the repo still satisfies the contract.
