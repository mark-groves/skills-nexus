#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def greeting(name):\n    return f"Hello, {name}"\n' > src/greeting.py
git add src/greeting.py
git commit -q -m 'feat: add greeting helper'
base_commit=$(git rev-parse HEAD)

git remote add origin https://github.com/contributor/widget-api.git
git remote add upstream https://github.com/example/widget-api.git
git update-ref refs/remotes/upstream/main "$base_commit"
git symbolic-ref refs/remotes/upstream/HEAD refs/remotes/upstream/main

git switch -q -c feat/friendly-greeting
git config branch.feat/friendly-greeting.pushRemote upstream
printf 'def greeting(name, excited=False):\n    suffix = "!" if excited else ""\n    return f"Hello, {name}{suffix}"\n' > src/greeting.py
git add src/greeting.py
git commit -q -m 'feat: support enthusiastic greetings'
