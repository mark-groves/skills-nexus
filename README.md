# skills-nexus

`skills-nexus` is a collection of reusable [Agent Skills](https://agentskills.io/)
and the tooling to install, validate, and evaluate them across supported agent
harnesses.

## Available skills

- `cloud-diagram` — create AWS, Azure, GCP, and multi-cloud draw.io diagrams
- `commit` — prepare intentional Git commits with conventional messages
- `drawio-shapes` — refresh and inspect draw.io cloud shape catalogs
- `pr` — push a branch and open a structured GitHub pull request
- `skill-architect` — design and improve portable Agent Skills

## Install a skill

Clone the repository, then select a harness and skill:

```bash
git clone https://github.com/mark-groves/skills-nexus.git
cd skills-nexus
bash scripts/deploy-skills.sh --harness codex --skill commit
```

Install all portable skills:

```bash
bash scripts/deploy-skills.sh --harness codex --all-portable
```

Supported harnesses are `agents`, `claude-code`, `codex`, `copilot`, `cursor`,
and `kiro`. User-level installation is the default. To install into a project:

```bash
bash scripts/deploy-skills.sh \
  --harness copilot \
  --skill pr \
  --scope project \
  --project-root /path/to/project
```

Use `--dry-run` to preview changes. See [Deployment](docs/deployment.md) for
selection, scopes, install modes, destinations, and update behavior.

## Work with the repository

Validate skills and the repository contract:

```bash
bash scripts/check-skills.sh
```

Preview an evaluation without running agent turns:

```bash
python3 scripts/eval_skills.py --skill skill-architect --plan
```

Repository guides:

- [Authoring skills](docs/authoring-skills.md)
- [Evaluating skills](docs/evaluating-skills.md)
- [Development and CI](docs/development.md)

## Layout

```text
skills/portable/           Cross-harness skills
skills/harness/<harness>/  Harness-specific skills
harnesses/                 User and project install destinations
scripts/                   Deployment, validation, and evaluation tools
tests/                     Repository tooling tests
```

Licensed under the [MIT License](LICENSE).
