# skills-nexus

`skills-nexus` is the portable home for reusable agent skills. The stable contract is simple: each skill lives in `skills/<name>/`, harness config stays thin, deployment is explicit, and repo validation is offline.

## Purpose

This repository keeps reusable skills in one place so they can be installed into different harnesses without changing the skill artifact itself. The top-level tooling exists to deploy those skills and to verify that the repo still matches the contract.

## Repo Contract

- `skills/<name>/` is the portable artifact.
- An immediate child of `skills/` is a valid skill only if it contains `SKILL.md`.
- Harness manifests are thin install-root JSON only, with the harness id inferred from the manifest filename.
- Top-level helper scripts are limited to install/deploy and validation concerns.
- `README.md` is the single repo guide.
- What this repo is not: no harness-specific skill variants, no shared runtime content outside skill folders, no generic automation dumping ground.

## Install/Deploy Usage

`--skill` is the primary path. `--all` is a convenience flag that deploys every immediate child of `skills/` that contains `SKILL.md`.

```bash
bash scripts/deploy-skills.sh --harness claude-code --skill commit --scope user
bash scripts/deploy-skills.sh --harness codex --skill pr --scope project --project-root /path/to/project
bash scripts/deploy-skills.sh --harness claude-code --all --dry-run
```

Use `--harness <name>` to select `harnesses/<name>.json`. The script stays neutral: it only chooses destination roots from the manifest and does not add overlays or harness-specific behavior.

## Validation

Run the repo validator with:

```bash
bash scripts/check-skills.sh
```

It checks the skill directory contract, optional `evals/evals.json` files, tracked generated junk, portability rules, backticked skill-local file references, thin harness manifests, and deploy dry-run behavior. The validator runs deterministically and offline.

## Maintainer Workflow For Shape-Catalog Refresh

1. Invoke the `drawio-shapes` skill to refresh the extracted draw.io data and produce provider-specific generated fragments.
2. Review the generated fragments before importing them anywhere else.
3. Invoke the `cloud-diagram` skill to validate and import those fragments into its bundled references.
4. Keep the generated fragments under review; the consumer skill owns mutation of its bundled references.
5. Rerun `bash scripts/check-skills.sh` to confirm the repo still satisfies the contract.
