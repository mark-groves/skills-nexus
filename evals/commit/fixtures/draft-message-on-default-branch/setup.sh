#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def normalize(value):\n    return value\n' > src/normalize.py
git add src/normalize.py
git commit -q -m 'feat: add value normalization'

printf 'def normalize(value):\n    return value.strip()\n' > src/normalize.py
