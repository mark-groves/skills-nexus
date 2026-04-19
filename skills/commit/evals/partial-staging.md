# Fixture: `partial-staging`

Repository state:
- `src/auth.py` contains staged hunks and separate unstaged hunks.
- No merge, rebase, cherry-pick, or revert is in progress.
- Branch is attached and not `main` or `master`.

Expected behavior:
- Commit only the staged hunks.
- Do not restage `src/auth.py`.
- Mention that unstaged hunks remain in the working tree.
