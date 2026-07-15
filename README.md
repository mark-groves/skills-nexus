# skills-nexus

`skills-nexus` is an evidence-driven foundry for reusable agent workflows. It
combines a publishable skill collection with tooling to author, evaluate,
package, deploy, observe, and improve skills across supported agent harnesses.

Canonical skills use the widely adopted `SKILL.md` directory conventions and a
deliberately minimal cross-client metadata core. The repository owns the
quality, evaluation, and promotion contract; target-specific permissions,
presentation, hooks, and plugin packaging belong in target integrations.

## Available skills

- `cloud-diagram` — create AWS, Azure, GCP, and multi-cloud draw.io diagrams
- `commit` — prepare intentional Git commits with conventional messages
- `drawio-shapes` — refresh and inspect draw.io cloud shape catalogs
- `pr` — push a branch and open a structured GitHub pull request
- `skill-architect` — design and improve reusable Agent Skills

## Install a skill

Use the community skills installer for normal cross-agent installation:

```bash
npx skills add mark-groves/skills-nexus --skill commit --agent codex
```

The repository also includes a local deployment helper for development and
controlled packaging:

```bash
git clone https://github.com/mark-groves/skills-nexus.git
cd skills-nexus
bash scripts/deploy-skills.sh --harness codex --skill commit
```

Install every canonical skill:

```bash
bash scripts/deploy-skills.sh --harness codex --all
```

Supported local deployment targets are `agents`, `claude-code`, `codex`,
`copilot`, `cursor`, and `kiro`. User-level symlinks are the default; project
installs use clean runtime copies. See [Deployment](docs/deployment.md).

## Evaluate and improve skills

Validate the repository contract:

```bash
bash scripts/check-skills.sh
```

Preview an evaluation without invoking agent turns:

```bash
python3 scripts/eval_skills.py --skill skill-architect --plan
```

Evaluation suites are repository-only evidence. They are stored separately
from runtime skills and are never included in packaged copies.

The first learning-loop component records bounded, structured observations from
real executions into a private inbox. Planned stages validate and triage that
evidence, turn accepted reports into regression cases, and compare candidate
changes against the current skill before a reviewed pull request can be
promoted. See [Continuous improvement](docs/continuous-improvement.md) and the
tracked [roadmap](ROADMAP.md).

## Repository layout

```text
skills/<name>/       Publishable skill instructions and runtime resources
evals/<name>/        Repository-only trigger cases, behavior cases, and fixtures
harnesses/           Local installation destinations for supported harnesses
scripts/             Packaging, deployment, evaluation, and observation tools
schemas/             Versioned interchange contracts for repository tooling
tests/               Repository tooling tests
```

Repository guides:

- [Authoring skills](docs/authoring-skills.md)
- [Evaluating skills](docs/evaluating-skills.md)
- [Continuous improvement](docs/continuous-improvement.md)
- [Development and CI](docs/development.md)

Licensed under the [MIT License](LICENSE).
