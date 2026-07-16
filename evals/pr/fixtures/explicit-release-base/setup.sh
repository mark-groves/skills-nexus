#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'VERSION = "1.0"\n' > src/version.py
git add src/version.py
git commit -q -m 'feat: add version module'
main_commit=$(git rev-parse HEAD)

git switch -q -c release/2026-04
printf 'VERSION = "1.1-rc1"\n' > src/version.py
git add src/version.py
git commit -q -m 'chore: prepare April release'
release_commit=$(git rev-parse HEAD)

git remote add origin https://github.com/example/widget-api.git
git update-ref refs/remotes/origin/main "$main_commit"
git update-ref refs/remotes/origin/release/2026-04 "$release_commit"
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c fix/release-version
printf 'VERSION = "1.1-rc2"\n' > src/version.py
git add src/version.py
git commit -q -m 'fix: correct release candidate version'
