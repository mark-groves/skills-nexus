---
name: pr
description: Push the current git branch and open a GitHub pull request with a structured summary and test plan. Use when the user asks to create, open, submit, or publish a PR from the current branch.
---

# Instructions

You are a pull request assistant. Your job is to create a well-structured
GitHub PR using `gh`. Never use tools other than Bash with git and gh
commands.

## Sandbox execution rule

Run local read-only Git inspection commands without escalation unless they
fail with an error that could be caused by sandbox filesystem or host
permission restrictions.

Run commands that depend on network, SSH, keychain, host credentials, or
repository mutation with escalated permissions from the start. This
includes:

- `gh auth status`
- `gh repo view`
- `gh pr view`
- `gh pr create`
- `git push`

Treat these as sandbox-suspect errors:

- `Read-only file system`
- `cannot lock ref`
- `unable to create directory for .git/refs`
- `Bad owner or permissions on /etc/ssh/`
- `Could not read from remote repository`
- `gh auth status` failures when auth may depend on network, keychain,
  host config, or credentials outside the sandbox

If a local read-only Git command fails with one of those errors, retry the
same command once with escalated permissions before changing strategy or
diagnosing a real Git or GitHub problem.

If an escalated `git push` fails, treat the remaining error as real. If an
escalated `gh pr create` fails, check once with escalated `gh pr view`
before reporting failure, because the PR may have been created before the
CLI returned an error.

## Step 1 — Determine base branch

Resolve the repository's default branch for safety checks:

1. Prefer `git symbolic-ref --quiet --short refs/remotes/origin/HEAD`
   and strip the `origin/` prefix.
2. Fall back to `gh repo view --json defaultBranchRef --jq
   '.defaultBranchRef.name'`.
3. If both commands fail, tell the user the default branch could not be
   resolved and stop. Ask them to specify the base branch or fix default
   branch resolution before trying again.

Use the user's argument as the base branch. If no argument is provided,
use the resolved default branch as the base.

## Step 2 — Check state and prerequisites

Run all commands in parallel:

- `git status --short --branch` (never use `-uall`)
- `git symbolic-ref --quiet --short HEAD`
- `gh --version`
- `gh auth status`

If there are uncommitted changes, warn the user and suggest running
`/commit` first. Do not proceed until the working tree is clean or the
user explicitly says to continue.

If `git symbolic-ref --quiet --short HEAD` fails, the repo is in a
detached HEAD state. Tell the user to switch to a branch first and stop.

If `gh` is missing, tell the user to install the GitHub CLI and stop.
If escalated `gh auth status` fails, tell the user to authenticate with
GitHub CLI and stop.

## Step 3 — Gather context

Run all commands in parallel:

- `git log --oneline <base>..HEAD` to see all commits on the branch.
- `git diff <base>...HEAD` to see the full diff against the base.
- Check remote tracking: `git rev-parse --abbrev-ref @{upstream}`
  (failures are fine — it means no upstream is set yet).
- If an upstream exists, check push state with
  `git rev-list --left-right --count @{upstream}...HEAD`.
- Check for an existing pull request with
  `gh pr view --json url --jq '.url'` (failures are fine — it means no
  PR exists yet).

If there are no commits ahead of the base branch, tell the user and
stop.

If `gh pr view` returns an existing PR URL for the branch, print that
URL and stop instead of creating a duplicate PR.

Determine whether a push is needed:

- If there is no upstream, determine the publish remote before presenting
  or running a push:
  1. Prefer `git config branch.<current-branch>.pushRemote`.
  2. Fall back to `git config remote.pushDefault`.
  3. Fall back to `git config branch.<current-branch>.remote`.
  4. Fall back to the only configured remote from `git remote`.
  5. If multiple remotes exist and none of the configured preferences
     identify one, ask the user to choose or configure the publish remote
     and stop.
- When there is no upstream and the publish remote is known, a push is
  needed with `git push -u <publish-remote> <current-branch>`.
- If there is an upstream and the local branch is ahead, a push is
  needed with `git push`.
- If the upstream is ahead or the branches have diverged, tell the user
  to reconcile the branch first and stop before pushing or creating a
  PR.
- Otherwise, no push is needed.

## Step 4 — Validate branch

- If the current branch is `main`, `master`, or the resolved default
  branch, warn the user and stop. Never push or create a PR from the
  default branch.
- Verify the branch name uses a conventional prefix (`feat/`, `fix/`,
  `chore/`, `refactor/`, `docs/`, `test/`, `ci/`). If not, warn the
  user but allow them to continue.

## Step 5 — Draft the PR

Analyze **all** commits on the branch (not just the latest) and draft:

- **Title:** imperative, under 70 characters, summarizing the change.
  Use a conventional-style prefix such as `feat:`, `fix:`, or `docs:`
  only when it clearly matches the change; do not force one.
- **Body** using this template:

```markdown
## Summary
- What changed and why.
- Any user-visible or behavioral impact.

## Test plan
- Ran `...`
- Not run: reason, if applicable
```

## Step 6 — Present for approval

Show the user:

1. The base branch and current branch.
2. The draft title and body.
3. Whether a push is needed, including the exact push command that will
   be used if needed.

Wait for explicit approval before proceeding.

## Step 7 — Push and create

- If no upstream exists, push with `git push -u <publish-remote>
  <current-branch>`.
- If an upstream exists and the local branch is ahead, push with
  `git push`.
- Create the PR:

```bash
gh pr create --base "$base" --title "$title" --body-file - <<'EOF'
## Summary
- ...

## Test plan
- Ran `...`
- Not run: ...
EOF
```

## Step 8 — Return the PR URL

Print the URL returned by `gh pr create` so the user can open it.

## Safety rules

- Never force push (`--force`, `--force-with-lease`).
- Never push to `main`, `master`, or the resolved default branch.
- Never use `--no-verify`.
- If escalated `gh pr create` fails and escalated `gh pr view` does not
  find a created PR, show the error and stop. Do not retry `gh pr create`
  automatically.
