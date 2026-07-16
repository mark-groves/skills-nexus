#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def audit():\n    return []\n' > src/audit.py
git add src/audit.py
git commit -q -m 'feat: add audit helper'
base_commit=$(git rev-parse HEAD)

git remote add origin https://github.com/engineering/widget-api.git
git remote add upstream https://github.com/example/widget-api.git
git update-ref refs/remotes/origin/main "$base_commit"
git update-ref refs/remotes/upstream/main "$base_commit"
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
git symbolic-ref refs/remotes/upstream/HEAD refs/remotes/upstream/main

git switch -q -c feat/org-fork
printf 'def audit():\n    return ["created"]\n' > src/audit.py
git add src/audit.py
git commit -q -m 'feat: record audit creation'
git config branch.feat/org-fork.pushRemote origin
