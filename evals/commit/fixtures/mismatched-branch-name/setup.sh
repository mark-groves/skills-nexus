#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def authenticate(token):\n    return bool(token)\n' > src/auth.py
git add src/auth.py
git commit -q -m 'feat: add authentication helper'

git switch -q -c docs/readme-typo
printf 'def authenticate(token, expired=False):\n    return bool(token) and not expired\n' > src/auth.py
