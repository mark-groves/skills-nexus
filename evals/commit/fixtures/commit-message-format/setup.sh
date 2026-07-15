#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'SESSION_TIMEOUT = 30\n\ndef session_expired(age):\n    return age > SESSION_TIMEOUT\n' > src/session.py
printf 'from session import session_expired\n\ndef test_session_expiry():\n    assert session_expired(31)\n' > src/session_test.py
git add src/session.py src/session_test.py
git commit -q -m 'feat(auth): add session expiry'

git switch -q -c feat/configurable-session-timeout
printf 'def session_expired(age, timeout=30):\n    return age > timeout\n' > src/session.py
printf 'from session import session_expired\n\ndef test_custom_session_expiry():\n    assert session_expired(61, timeout=60)\n' > src/session_test.py
