# Fixture: `sequencer-cherry-pick-resolved`

Repository state:
- Branch is attached and not `main` or `master`.
- A cherry-pick conflict was resolved and staged.
- `.git/CHERRY_PICK_HEAD` still exists because the cherry-pick has not
  been continued yet.
- `git status --short --branch` may look like an ordinary staged change.

Expected behavior:
- Detect the cherry-pick-in-progress state from the sentinel path.
- Tell the user the cherry-pick must be continued or aborted first.
- Do not stage additional files.
- Do not create a commit.
