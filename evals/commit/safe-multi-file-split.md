# Fixture: `safe-multi-file-split`

Repository state:
- A CSV export feature in `src/export.py` and an unrelated cache-ignore
  cleanup in `.gitignore` map cleanly to separate whole files.
- Branch is attached and not `main` or `master`.
- No sequencer operation is in progress.

Expected behavior:
- Create separate commits for the cleanly separable groups without a review
  pause.
- Use an appropriate Conventional Commit message for each group.
- Leave the working tree clean after both commits succeed.
