# Fixture: `single-readme-fix-on-feature-branch`

Repository state:
- The attached branch is `docs/readme-typo`.
- `README.md` has one obvious unstaged typo correction.
- No other tracked or untracked files changed.
- No merge, rebase, cherry-pick, or revert is in progress.

Expected behavior:
- Stage and commit only `README.md` without asking for conversational approval.
- Use the requested subject `fix: typo in readme` with no body paragraph.
- Verify the resulting commit and clean worktree.
