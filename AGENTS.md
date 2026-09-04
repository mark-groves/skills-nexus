# AGENTS.md

This file is caveats only. Standard commands live in `README.md` and
`docs/development.md`.

- `bash scripts/check-quality.sh` needs ShellCheck as a system binary, not from
  pip. `actionlint` comes from the `actionlint-py` package inside `.venv`.
  Missing ShellCheck fails the script.
- Behavioral prove work uses Cursor Cloud Agents. It is optional and not
  required for tests, validation, or deployment. See
  `docs/evaluating-skills.md` and
  `docs/adr/0001-cloud-agent-eval-orchestration.md`.
- Aesthetic draw.io proof screenshots need the official draw.io desktop CLI.
  Install with `bash scripts/install-drawio-cli.sh`, then export via
  `plugins/drawio/skills/cloud-diagram/scripts/`. Never use
  `npx drawio-headless`. It omits provider icons.
