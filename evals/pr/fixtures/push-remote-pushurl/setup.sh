#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def transport():\n    return "https"\n' > src/transport.py
git add src/transport.py
git commit -q -m 'feat: add transport helper'
base_commit=$(git rev-parse HEAD)

git remote add origin https://github.com/contributor/widget-api.git
git remote set-url --add --push origin git@github.com:contributor/widget-api.git
git remote add upstream https://github.com/example/widget-api.git
git update-ref refs/remotes/origin/main "$base_commit"
git update-ref refs/remotes/upstream/main "$base_commit"
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
git symbolic-ref refs/remotes/upstream/HEAD refs/remotes/upstream/main

git switch -q -c feat/transport
printf 'def transport():\n    return "ssh"\n' > src/transport.py
git add src/transport.py
git commit -q -m 'feat: support ssh transport'
git update-ref refs/remotes/upstream/feat/transport "$base_commit"
git branch --set-upstream-to=upstream/feat/transport >/dev/null
git config branch.feat/transport.pushRemote origin
git config remote.pushDefault upstream
