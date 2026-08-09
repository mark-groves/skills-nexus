# skills-nexus

`skills-nexus` is an evidence-driven foundry for reusable agent workflows. It
packages companion skills as [Agent Plugins](https://agent-plugins.org/) and
keeps repository-owned evaluation, validation, and improvement tooling beside
them.

Canonical skills use the widely adopted `SKILL.md` directory conventions and a
deliberately minimal cross-client metadata core. The repository owns the
quality, evaluation, and promotion contract; client-specific presentation and
hooks stay outside the portable plugin package.

## Available plugins

| Plugin | Skills |
| --- | --- |
| `git-workflow` | `commit`, `pr` |
| `drawio` | `cloud-diagram`, `drawio-shapes` |
| `skill-architect` | `skill-architect` |

## Install

Primary path for Cursor: copy a plugin directory into the local plugins root
(see Cursor's Agent Plugins docs). Prefer `rsync` over repo symlinks:

```bash
mkdir -p ~/.cursor/plugins/local
rsync -a --delete "$PWD/plugins/git-workflow/" ~/.cursor/plugins/local/git-workflow/
```

For harness skill-root installs during development, the local helper expands a
skill selector to its owning companion bundle:

```bash
git clone https://github.com/mark-groves/skills-nexus.git
cd skills-nexus
bash scripts/deploy-skills.sh --harness cursor --skill commit
# installs commit and pr together
```

Install every canonical skill (all bundles):

```bash
bash scripts/deploy-skills.sh --harness cursor --all
```

Supported local deployment targets are `agents`, `claude-code`, `codex`,
`copilot`, `cursor`, and `kiro`. See [Deployment](docs/deployment.md).

## Evaluate and improve skills

Validate the repository contract:

```bash
bash scripts/check-skills.sh
```

Preview an evaluation without invoking agent turns:

```bash
python3 scripts/eval_skills.py --skill skill-architect --plan
```

Preview the bounded routine screen for a candidate:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate /path/to/candidate-skill \
  --workflow routine \
  --plan
```

Routine screens are report-only. A positive result is only eligible for a
human-opted full escalation; it never approves or promotes a candidate.

Preview repository-owned component boundaries before running backward
elimination:

```bash
python3 scripts/ablate_skill_components.py \
  --skill skill-architect \
  --case-groups /path/to/review-case-groups.json \
  --plan
```

Evaluation suites are repository-only evidence. They are stored separately
from runtime skills and are never included in packaged copies.

The first learning-loop component records bounded, structured observations from
real executions into a private inbox. Planned stages validate and triage that
evidence, turn accepted reports into regression cases, and compare candidate
changes against the current skill before a reviewed pull request can be
promoted. See [Continuous improvement](docs/continuous-improvement.md) and the
tracked [roadmap](ROADMAP.md). The
[Capability optimisation](docs/capability-optimisation.md) guide defines the
evidence contract for planned context reduction and retirement reviews.

## Repository layout

```text
plugins/<bundle>/    Agent Plugin packages (plugin.json + skills/<name>/)
evals/<name>/        Repository-only trigger cases, behavior cases, and fixtures
harnesses/           Local installation destinations for supported harnesses
scripts/             Packaging, deployment, evaluation, and observation tools
schemas/             Versioned interchange contracts for repository tooling
tests/               Repository tooling tests
```

Repository guides:

- [Authoring skills](docs/authoring-skills.md)
- [Deployment](docs/deployment.md)
- [Cloud Agent ops](docs/cloud-agent-ops.md)
- [Evaluating skills](docs/evaluating-skills.md)
- [Continuous improvement](docs/continuous-improvement.md)
- [Capability optimisation](docs/capability-optimisation.md)
- [Development and CI](docs/development.md)

Licensed under the [MIT License](LICENSE).
