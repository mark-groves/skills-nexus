# Development and CI

Python 3.11 or newer is supported for local repository tooling. Create a virtual
environment and install the pinned development tools:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --requirement requirements-dev.txt
```

## Local checks

Run the test suite and repository contract validator:

```bash
bash scripts/check-skills.sh
```

Run formatting, linting, type checking, shell analysis, workflow checks, and
static security analysis:

```bash
bash scripts/check-quality.sh
```

Audit pinned development dependencies:

```bash
pip-audit --requirement requirements-dev.txt --strict
```

`check-quality.sh` runs Ruff, the Ruff formatter check, mypy, ShellCheck,
actionlint, Bandit, and zizmor. The quality tools must be installed before the
script is run.

## Continuous integration

GitHub Actions runs repository tests and contract validation on Python 3.11 and
3.14. Separate jobs run static and security analysis, audit Python development
dependencies, and review dependency changes on pull requests. CodeQL analyzes
Python changes and runs weekly.

Workflow actions are pinned to immutable commits. Dependabot checks weekly for
updates to GitHub Actions and Python development dependencies.
