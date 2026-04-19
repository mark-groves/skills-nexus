# Fixture: `safe-multi-file-split`

Repository state:
- Multiple unrelated changes map cleanly to separate whole files, or to
  hunks the user already staged intentionally.
- Branch is attached and not `main` or `master`.
- No sequencer operation is in progress.

Expected behavior:
- Propose separate commits for the cleanly separable groups.
- Present all groups and draft messages before executing anything.
- Leave rejected groups untouched in the working tree.
