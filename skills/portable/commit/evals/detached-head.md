# Fixture: `detached-head`

Repository state:
- HEAD is detached.
- There may be staged or unstaged file changes.
- `git symbolic-ref --quiet --short HEAD` fails.

Expected behavior:
- Warn that committing on detached HEAD is unsafe.
- Do not stage any files.
- Do not create a commit.
