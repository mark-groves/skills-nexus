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

For Cursor, copy a plugin into `~/.cursor/plugins/local/` with `rsync`. Do not
symlink out of the repo; Cursor rejects that.

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

Supported local deployment targets are `agents`, `claude-code`, `copilot`,
`cursor`, and `kiro`. See [Deployment](docs/deployment.md).

## Evaluate and improve skills

Validate the repository contract:

```bash
bash scripts/check-quality.sh
bash scripts/check-skills.sh
```

`evals/<skill>/evals.json` is the case catalog. `scripts/eval_cases.py` loads
it for validation, observation promote, and packaging. Those commands do not
spawn agents.

The Codex live matrix is gone. Behavioral proof is a Cloud Agent prove path.
See the [orchestration playbook](docs/eval-orchestration.md),
[Evaluating skills](docs/evaluating-skills.md), and
[ADR 0001](docs/adr/0001-cloud-agent-eval-orchestration.md).

The learning loop records bounded observations, then redacts, classifies, and
either rejects them or promotes accepted evidence into `evals.json`. See
[Continuous improvement](docs/continuous-improvement.md) and the
[roadmap](ROADMAP.md).

## Repository layout

```text
plugins/<bundle>/    Agent Plugin packages (plugin.json + skills/<name>/)
evals/<name>/        Repository-only trigger cases, behavior cases, and fixtures
harnesses/           Local installation destinations for supported harnesses
scripts/             Packaging, deployment, catalog load, and observation tools
schemas/             Versioned interchange contracts for repository tooling
tests/               Repository tooling tests
```

Repository guides:

- [Authoring skills](docs/authoring-skills.md)
- [Deployment](docs/deployment.md)
- [Evaluating skills](docs/evaluating-skills.md)
- [Continuous improvement](docs/continuous-improvement.md)
- [Capability optimisation](docs/capability-optimisation.md)
- [Development and CI](docs/development.md)

Licensed under the [MIT License](LICENSE).
