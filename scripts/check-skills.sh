#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m unittest discover -s "$REPO_DIR/tests"
exec python3 "$REPO_DIR/scripts/validate_repo.py" "$@"
