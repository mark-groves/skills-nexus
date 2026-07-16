#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def greeting(name):\n    return f"Hello, {name}"\n' > src/greeting.py
git add src/greeting.py
git commit -q -m 'feat: add greeting helper'

git remote add origin https://github.com/example/widget-api.git
git switch -q -c feat/friendly-greeting
printf 'def greeting(name, excited=False):\n    suffix = "!" if excited else ""\n    return f"Hello, {name}{suffix}"\n' > src/greeting.py
git add src/greeting.py
git commit -q -m 'feat: support enthusiastic greetings'
