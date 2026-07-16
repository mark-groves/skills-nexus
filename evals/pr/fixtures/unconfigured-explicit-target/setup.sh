#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def greeting():\n    return "hello"\n' > src/greeting.py
git add src/greeting.py
git commit -q -m 'feat: add greeting helper'
base_commit=$(git rev-parse HEAD)

git remote add origin https://github.com/contributor/widget-api.git
git update-ref refs/remotes/origin/main "$base_commit"
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/explicit-target
printf 'def greeting():\n    return "hello!"\n' > src/greeting.py
git add src/greeting.py
git commit -q -m 'feat: add enthusiastic greeting'
