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

Evaluate one skill without spending agent turns yet:

```bash
python3 scripts/eval_skills.py --skill skill-architect --plan
```

Run a focused efficacy comparison:

```bash
python3 scripts/eval_skills.py \
  --skill skill-architect \
  --trigger-case 3 \
  --behavior-case 4
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
  `pr`, and a future `harness/codex/example` skill would install as
  `example`.
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
- Codex harness skills under `skills/harness/codex/<name>/` must keep
  deployable `SKILL.md` frontmatter to Codex runtime-safe fields:
  `name`, `description`, and optional `metadata`. Put compatibility,
  harness assumptions, and workflow prerequisites in the Markdown body,
  not in frontmatter.
- Skill-local support files may live under `scripts/`, `references/`,
  `assets/`, and `evals/`.
- Skill package names must be unique across portable and harness-specific
  skills so deployment cannot collide.
- Harness manifests stay thin and define install roots only.

## Deployment Notes

`--skill` is the primary deployment path. It accepts a full skill id such
as `portable/pr` or `harness/<harness>/<name>`; a bare skill name such as
`pr` is accepted only when it is unambiguous.

`--all` installs every portable skill plus every skill under
`skills/harness/<selected-harness>/`. Use `--all-portable` for portable
skills only, or `--all-for-harness` for harness-specific skills only.

`symlink` is the default mode for most user-scoped installs so edits in this repository show up immediately in installed skills. Codex user-scoped installs default to `copy` because Codex skill discovery must see real skill directories. `copy` is also the default mode for project-scoped installs so deployed skills are normal project files.

Use `--dry-run` to inspect the install actions before making changes.

For project-scoped installs, pass `--scope project --project-root /path/to/project`.

## Validation

`scripts/check-skills.sh` runs the repository validator in offline, deterministic mode. It checks the skill directory contract, supported frontmatter, Codex harness frontmatter constraints, portability rules, thin harness manifests, deployment behavior, and repository-specific generated-content workflows.

## Continuous Integration

GitHub Actions runs the repository tests and contract validator on Python 3.11
and 3.14. A separate quality gate runs Ruff, Ruff's formatter check, mypy,
ShellCheck, actionlint, Bandit, and zizmor. Development-tool dependencies are
audited with `pip-audit`, pull requests receive GitHub dependency review, and
CodeQL performs extended Python security analysis on changes plus a weekly
schedule.

Actions are pinned to immutable commit SHAs and use read-only permissions unless
a job needs the CodeQL `security-events: write` permission. Dependabot proposes
weekly updates for both the pinned actions and Python quality tools.

Run the same checks locally with Python 3.11 or newer:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
bash scripts/check-skills.sh
bash scripts/check-quality.sh
pip-audit --requirement requirements-dev.txt --strict
```

For protected branches, require `Static and security analysis`, both Python test
matrix jobs, `Python dependency audit`, `Dependency review`, and `CodeQL
(Python)`. GitHub treats the dependency-review job as skipped (and therefore
successful) for non-pull-request events.

## Skill Evals

`scripts/eval_skills.py` turns each skill's `evals/evals.json` into an
executable experiment. Trigger cases measure whether Codex reads the selected
skill in a clean context. Behavior cases run twice from identical fixtures:
once with a sanitized copy of the skill and once without it. A third,
label-blinded judge turn grades both candidates against the same observable
checks.

By default, sanitized copies of the repository's other Codex-deployable skills
(portable skills plus Codex harness skills) are available in both conditions.
The behavior baseline removes only the selected skill, and trigger tests can
select among the same peers they encounter after deployment. Use
`--skill-universe isolated` when measuring the selected skill alone.

The evaluator deliberately removes `evals/` from the installed task copy so
expected answers cannot leak into the run, and applies the same runtime
frontmatter filtering as Codex copy deployment. It records activation,
commands, final responses, workspace deltas, Git state, timing, tokens, tool
calls, check-level evidence, baseline lift, and confidence limitations. Each
run writes:

- `results.json` for automation and longitudinal analysis;
- `report.md` for review in Git or a terminal;
- `report.html` for a self-contained visual review;
- `runs/` with prompts, JSONL event traces, task workspaces, and grader output.

Reports default to `.skill-evals/`, which is ignored by Git. Use `--plan` to
estimate the number of agent turns, `--jobs` to control concurrency,
`--trigger-repeats` and `--behavior-repeats` to measure variance, and
`--fail-under` to add an efficacy gate in CI. `codex login` must already have
created an auth file; the evaluator links it into a temporary isolated Codex
home and deletes that home after every turn.

Fixture references are resolved relative to the selected skill. Files under
`evals/fixtures/<scenario>/` are copied into the workspace with the scenario
prefix removed. An optional root `setup.sh` in that directory can build staged
Git state or other deterministic inputs; nested files named `setup.sh` remain
ordinary fixture content. The root hook receives `EVAL_WORKSPACE` and
`EVAL_SKILL_DIR` in a minimal environment without inherited credentials. Legacy
Markdown fixture recipes are supported, but expected
behavior sections are withheld and the report marks their fidelity as
`description-only`. Missing or failed fixtures are never hallucinated: those
checks are reported as unknown.
