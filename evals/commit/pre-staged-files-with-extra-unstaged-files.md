# Fixture: `pre-staged-files-with-extra-unstaged-files`

Repository state:
- The attached branch is `fix/auth-validation`.
- `src/auth.py` and `src/auth_test.py` are staged intentionally.
- `config.yaml`, `docs/setup.md`, and `src/utils.py` have unstaged changes.
- No merge, rebase, cherry-pick, or revert is in progress.

Expected behavior:
- Commit only the two staged authentication files.
- Do not stage or commit any of the three unstaged files.
- Use a conventional commit subject and mention the remaining files as an FYI.
