# AGENTS.md

This file is caveats only. Standard commands live in `README.md` and
`docs/development.md`.

- `bash scripts/check-quality.sh` needs ShellCheck as a system binary, not from
  pip. `actionlint` comes from the `actionlint-py` package inside `.venv`.
  Missing ShellCheck fails the script.
- Live skill evaluation (runs without `--plan`) needs the Codex CLI,
  credentials, and network access. It is optional and not required for tests,
  validation, or deployment. See `README.md` and `docs/` for `--plan` and the
  eval scripts.
- Aesthetic draw.io proof screenshots need the official draw.io desktop CLI.
  Install with `bash scripts/install-drawio-cli.sh`, then export via
  `plugins/drawio/skills/cloud-diagram/scripts/`. Never use
  `npx drawio-headless`. It omits provider icons.
