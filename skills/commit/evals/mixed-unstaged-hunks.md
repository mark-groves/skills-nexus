# Fixture: `mixed-unstaged-hunks`

Repository state:
- One unstaged file contains unrelated logical changes in separate hunks.
- Nothing relevant is already staged.
- No sequencer operation is in progress.

Expected behavior:
- Do not propose automatic split commits for those unstaged hunks.
- Do not use interactive staging.
- Tell the user to pre-stage the intended hunks or accept a single
  commit.
