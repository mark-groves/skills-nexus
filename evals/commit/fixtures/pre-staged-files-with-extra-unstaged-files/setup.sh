#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src docs
printf 'def authenticate(token):\n    return bool(token)\n' > src/auth.py
printf 'def test_authenticate():\n    assert True\n' > src/auth_test.py
printf 'timeout: 30\n' > config.yaml
printf '# Setup\n' > docs/setup.md
printf 'def normalize(value):\n    return value\n' > src/utils.py
git add src/auth.py src/auth_test.py config.yaml docs/setup.md src/utils.py
git commit -q -m 'feat: add authentication skeleton'

git switch -q -c feat/auth-expiry
printf 'def authenticate(token, expired=False):\n    return bool(token) and not expired\n' > src/auth.py
printf 'from auth import authenticate\n\ndef test_expired_token():\n    assert not authenticate("token", expired=True)\n' > src/auth_test.py
git add src/auth.py src/auth_test.py

printf 'timeout: 45\n' > config.yaml
printf '# Setup\n\nSet the service timeout before starting.\n' > docs/setup.md
printf 'def normalize(value):\n    return value.strip()\n' > src/utils.py
