#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

ruff check .
ruff format --check .
mypy
git ls-files -z '*.sh' | xargs -0 --no-run-if-empty shellcheck
actionlint
bandit \
  --configfile pyproject.toml \
  --recursive scripts skills \
  --severity-level medium
zizmor \
  --min-severity medium \
  --offline \
  --strict-collection \
  .github
