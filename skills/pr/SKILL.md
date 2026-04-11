---
name: pr
description: Push the current branch and open a GitHub pull request with a structured summary and test plan. Use when the user asks to create, open, or submit a PR.
user-invocable: true
allowed-tools:
  - Bash
argument-hint: "[base-branch]"
---

# Instructions

You are a pull request assistant. Your job is to create a well-structured
GitHub PR using `gh`. Never use tools other than Bash with git and gh
commands.

## Step 1 — Determine base branch

Use the user's argument as the base branch. Default to `main` if no
argument is provided.

## Step 2 — Check state and prerequisites

Run all commands in parallel:

- `git status` (never use `-uall`)
- `gh --version`

If there are uncommitted changes, warn the user and suggest running
`/commit` first. Do not proceed until the working tree is clean or the
user explicitly says to continue.

If `gh` is missing, tell the user to install the GitHub CLI and stop.

## Step 3 — Gather context

Run all commands in parallel:

- `git log --oneline <base>..HEAD` to see all commits on the branch.
- `git diff <base>...HEAD` to see the full diff against the base.
- Check remote tracking: `git rev-parse --abbrev-ref @{upstream}`
  (failures are fine — it means no upstream is set yet).

If there are no commits ahead of the base branch, tell the user and
stop.

## Step 4 — Validate branch

- If the current branch is `main` or `master`, warn the user and stop.
  Never push or create a PR from the default branch.
- Verify the branch name uses a conventional prefix (`feat/`, `fix/`,
  `chore/`, `refactor/`, `docs/`, `test/`, `ci/`). If not, warn the
  user but allow them to continue.

## Step 5 — Draft the PR

Analyze **all** commits on the branch (not just the latest) and draft:

- **Title:** under 70 characters, summarizing the change.
- **Body** using this template:

```markdown
## Summary
- bullet 1
- bullet 2

## Test plan
- [ ] step 1
- [ ] step 2
```

## Step 6 — Present for approval

Show the user:

1. The base branch and current branch.
2. The draft title and body.
3. Whether a push is needed.

Wait for explicit approval before proceeding.

## Step 7 — Push and create

- Push with `-u` if the branch has no upstream tracking.
- Create the PR:

```bash
gh pr create --title "the title" --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...
EOF
)"
```

## Step 8 — Return the PR URL

Print the URL returned by `gh pr create` so the user can open it.

## Safety rules

- Never force push (`--force`, `--force-with-lease`).
- Never push to `main` or `master`.
- Never use `--no-verify`.
- If `gh pr create` fails, show the error and stop. Do not retry
  automatically.
