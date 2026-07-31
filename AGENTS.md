# AGENTS.md

## Cursor Cloud specific instructions

`skills-nexus` is a Python 3.11+ CLI/tooling repo (no runtime services, servers, or
databases); it runs via Python scripts and Bash wrappers. Local validation
(`check-skills.sh`, `check-quality.sh`), skill deployment, and `--plan` evaluation
run fully offline. The one exception is live (non-`--plan`) skill evaluation, which
invokes the Codex CLI and requires network access plus credentials (see the last
bullet). Standard commands live in `README.md` and `docs/development.md`; only
non-obvious caveats are noted here.

- A Python virtualenv is provided at `.venv` (dev/quality tools from
  `requirements-dev.txt` are installed there by the startup update script). Activate it
  before running anything: `. .venv/bin/activate` (or call binaries directly, e.g.
  `.venv/bin/ruff`). The tools are not on the system `PATH` without it.
- Tests + repo contract validation: `bash scripts/check-skills.sh`
  (`unittest discover tests/` then `scripts/validate_repo.py`).
- Lint/type/security: `bash scripts/check-quality.sh` runs ruff, `ruff format --check`,
  mypy, ShellCheck, actionlint, Bandit, and zizmor. `actionlint` is provided by the
  `actionlint-py` pip package (inside `.venv`), but **ShellCheck is a system binary**
  (`apt install shellcheck`) captured in the VM snapshot, not a pip dependency — the
  script fails if it is missing.
- Running the product: `bash scripts/deploy-skills.sh --harness <target> --skill <name>`
  (or `--all`). With default user scope this installs into `~/.agents/skills` (outside
  the repo), so deployments do not create git changes.
- Skill evaluation scripts (`eval_skills.py`, `review_skill_capability.py`,
  `ablate_skill_components.py`) all support a `--plan` dry-run that needs no external
  service. Live (non-`--plan`) runs require the Codex CLI on `PATH` plus credentials
  (`CODEX_API_KEY` or `~/.codex/auth.json`) and network access — optional, not needed
  for tests/validation/deployment.
