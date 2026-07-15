#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src tests
printf 'def greeting(name):\n    return f"Hello, {name}"\n' > src/greeting.py
printf 'import unittest\n\nclass GreetingTest(unittest.TestCase):\n    def test_placeholder(self):\n        self.assertTrue(True)\n' > tests/test_greeting.py
git add src/greeting.py tests/test_greeting.py
git commit -q -m 'feat: add greeting helper'
base_commit=$(git rev-parse HEAD)

git remote add origin https://github.com/example/widget-api.git
git update-ref refs/remotes/origin/main "$base_commit"
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/friendly-greeting
printf 'def greeting(name, excited=False):\n    suffix = "!" if excited else ""\n    return f"Hello, {name}{suffix}"\n' > src/greeting.py
printf 'import unittest\n\nfrom src.greeting import greeting\n\nclass GreetingTest(unittest.TestCase):\n    def test_excited_greeting(self):\n        self.assertEqual(greeting("Ada", excited=True), "Hello, Ada!")\n' > tests/test_greeting.py
git add src/greeting.py tests/test_greeting.py
git commit -q -m 'feat: support enthusiastic greetings'
