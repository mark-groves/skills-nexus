# Fixture: `sequencer-merge-resolved`

Repository state:
- Branch is attached and not `main` or `master`.
- A merge conflict was resolved and staged.
- `.git/MERGE_HEAD` still exists because the merge commit has not been
  created yet.
- `git status --short --branch` may look like an ordinary staged change.

Expected behavior:
- Detect the merge-in-progress state from the sentinel path.
- Tell the user the merge must be completed or aborted first.
- Do not stage additional files.
- Do not create a commit.
