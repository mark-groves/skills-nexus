#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def record_event(event):\n    return event\n' > src/audit.py
git add src/audit.py
git commit -q -m 'feat: add audit helper'
base_commit=$(git rev-parse HEAD)

git remote add origin ssh://git@github.corp.example/platform/widget-api.git
git update-ref refs/remotes/origin/main "$base_commit"
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/audit-events
printf 'def record_event(event):\n    return {"event": event}\n' > src/audit.py
git add src/audit.py
git commit -q -m 'feat: structure audit events'
