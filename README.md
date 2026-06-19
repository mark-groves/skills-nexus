# skills-nexus

Reusable agent skills aligned with the
[open Agent Skill standard](https://agentskills.io/home), with a
simple repository contract for both portable skills and reusable
harness-specific skills:

- portable skills live in `skills/portable/<name>/`
- harness-specific skills live in `skills/harness/<harness>/<name>/`
- a directory is a valid skill when it contains `SKILL.md`
- deployment is explicit through `scripts/deploy-skills.sh`
- validation is offline through `scripts/check-skills.sh`

Project-specific skills do not live here. Put them in the project repo
they describe.

## Quick Start

Use `--harness <name>` to select `harnesses/<name>.json`.

Deploy one skill:

```bash
bash scripts/deploy-skills.sh --harness codex --skill portable/pr --scope user
```

Deploy multiple portable skills using unambiguous short names:

```bash
bash scripts/deploy-skills.sh --harness agents --skill commit --skill pr --scope user
```

Deploy a Codex-specific skill:

```bash
bash scripts/deploy-skills.sh --harness codex --skill harness/codex/codex-pr-review-loop --scope user
```

Deploy every portable skill plus every skill for the selected harness:

```bash
bash scripts/deploy-skills.sh --harness codex --all --mode copy
```

Deploy only portable skills:

```bash
bash scripts/deploy-skills.sh --harness cursor --all-portable --mode copy
```

Deploy one skill into a Copilot project:

```bash
bash scripts/deploy-skills.sh --harness copilot --skill portable/pr --scope project --project-root /path/to/project
```

Validate the repository:

```bash
bash scripts/check-skills.sh
```

## Repository Layout

```text
skills/portable/           Portable skill artifacts
skills/harness/<harness>/  Reusable harness-specific skill artifacts
harnesses/                 Install roots for supported clients
scripts/                   Deploy and validation entrypoints
tests/                     Validator coverage
```

Supported harness manifests:

- `agents`
- `claude-code`
- `codex`
- `copilot`
- `cursor`
- `kiro`

## Skill Contract

- `skills/portable/<name>/` is the canonical portable artifact.
- `skills/harness/<harness>/<name>/` is the canonical artifact for a
  reusable harness-specific skill.
- Deployed skills are installed by their package folder name, not by
  their repository category path. For example, `portable/pr` installs as
  `pr`, and `harness/codex/codex-pr-review-loop` installs as
  `codex-pr-review-loop`.
- Canonical `SKILL.md` frontmatter follows the open Agent Skills
  standard:
  - `name` is required, must match the folder name, and uses 1-64
    lowercase alphanumeric or hyphen characters with no leading,
    trailing, or repeated hyphens.
  - `description` is required, non-empty, and at most 1024 characters.
  - `license`, `compatibility`, `metadata`, and `allowed-tools` are
    optional standard fields.
  - `compatibility`, when present, is non-empty and at most 500
    characters.
  - `metadata`, when structured, is a string-to-string map.
  - `allowed-tools` is accepted as the standard experimental
    space-separated tool allowlist.
- Skill-local support files may live under `scripts/`, `references/`,
  `assets/`, and `evals/`.
- Skill package names must be unique across portable and harness-specific
  skills so deployment cannot collide.
- Harness manifests stay thin and define install roots only.

## Deployment Notes

`--skill` is the primary deployment path. It accepts a full skill id such
as `portable/pr` or `harness/codex/codex-pr-review-loop`; a bare skill
name such as `pr` is accepted only when it is unambiguous.

`--all` installs every portable skill plus every skill under
`skills/harness/<selected-harness>/`. Use `--all-portable` for portable
skills only, or `--all-for-harness` for harness-specific skills only.

`symlink` is the default mode for user-scoped installs so edits in this repository show up immediately in installed skills. `copy` is the default mode for project-scoped installs so deployed skills are normal project files.

Use `--dry-run` to inspect the install actions before making changes.

For project-scoped installs, pass `--scope project --project-root /path/to/project`.

## Validation

`scripts/check-skills.sh` runs the repository validator in offline, deterministic mode. It checks the skill directory contract, supported frontmatter, portability rules, thin harness manifests, deployment behavior, and repository-specific generated-content workflows.
