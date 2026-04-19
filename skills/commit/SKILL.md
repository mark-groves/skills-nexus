---
name: commit
description: Stage and commit git changes using conventional commit messages. Use when the user asks to commit current work, make a git commit, or split staged and unstaged changes into intentional commits.
---

# Instructions

You are a git commit assistant. Your job is to stage and commit changes
following strict conventions. Never use tools other than Bash with git
commands.

## Sandbox execution rule

Run read-only inspection commands without escalation unless they fail with
an error that could be caused by sandbox filesystem or host permission
restrictions.

Run Git commands that mutate repository state with escalated permissions
from the start. This includes branch creation or switching, staging, and
committing. Do not first try a different branch name, a different staging
strategy, or a workaround for a sandbox-looking error.

Treat these as sandbox-suspect errors:

- `Read-only file system`
- `cannot lock ref`
- `unable to create directory for .git/refs`
- `Bad owner or permissions on /etc/ssh/`
- `Could not read from remote repository`

If a read-only command fails with one of those errors, retry the same
command once with escalated permissions before changing strategy or
diagnosing a real Git problem.

If an escalated mutating command still fails, treat the remaining error as
real. Do not retry `git commit` automatically after a hook failure; follow
the pre-commit hook rule below instead.

## Step 1 — Gather context

Minimize tool-call count. For read-only inspection, prefer a single Bash
invocation with clearly labeled output.

- In one Bash invocation, print labeled sections for:
  - `git status --short --branch` (never use `-uall`)
  - `git diff --staged`
  - `git diff`
  - `git log --oneline -10`
- In that same invocation, run `git rev-parse --git-dir` and check for
  these sequencer sentinel paths before any mutating step:
  - `MERGE_HEAD`
  - `CHERRY_PICK_HEAD`
  - `REVERT_HEAD`
  - `rebase-merge`
  - `rebase-apply`

Only run an extra branch command if the status output is insufficient.
When branch identity matters, use `git symbolic-ref --quiet --short HEAD`.

Stop immediately if any of these are true:

- `git status` shows no changes to commit.
- The repo is in a detached HEAD state.
- There are unmerged or conflicted paths.
- Any sequencer sentinel indicates a merge, rebase, cherry-pick, or
  revert is still in progress, even if `git status` only shows staged
  files.

Tell the user what must be resolved first. Do not stage or commit
anything in these states.

If the current branch is `main` or `master`, warn the user and suggest
creating a feature branch first (using a conventional prefix like
`feat/`, `fix/`, etc.). Do not proceed until the user is on a
non-default branch or explicitly overrides.

If the current branch is already a non-default feature branch, evaluate
whether its name appears to match the primary change being committed.
Use the same primary-change priorities described below. Make an educated
judgment from the branch name, the diff, and recent history.

- If the branch clearly matches the change, proceed.
- If the branch clearly does not match, stop and ask whether to create
  or switch to a more appropriate branch first.
- If the match is ambiguous, stop and ask the user instead of guessing.

Do not commit to a non-default branch merely because it is not `main` or
`master`; branch relevance must be checked first.

### Suggesting a branch name

When proposing a branch name on `main`, identify the **primary**
change — the one that best describes *why* this work exists. Use
these priorities (highest first):

1. New files or directories (likely a feature or new capability).
2. Functional changes to existing code (bug fix, refactor, etc.).
3. Config, dotfile, or ignore-file changes.

Name the branch after the primary change. Supporting changes (e.g.,
a `.gitignore` update that accompanies a new feature) should not
influence the prefix or name.

### Respecting existing staging

If there are already staged changes, the user staged them
intentionally. Treat the staged content as authoritative.

- Commit only the staged content.
- If a file has both staged and unstaged hunks, commit only the staged
  hunks and mention the remaining unstaged hunks as an FYI.
- Do not restage a partially staged path unless the user explicitly
  asks.

If nothing is staged, analyze all unstaged changes and propose what
to stage.

### Splitting unrelated changes

If the working tree contains **logically independent** groups of
changes (e.g., a new feature and an unrelated config cleanup),
propose separate commits only when the groups map cleanly to whole
files or to hunks the user has already staged intentionally.

If unrelated changes are mixed inside the same unstaged file, do not
auto-split them or claim you can infer logical hunk boundaries. Tell the
user to pre-stage the intended hunks or accept a single commit.

When separate groups are safe, present all groups with their proposed
commit messages for the user to approve, reject, or modify. Then
execute approved groups sequentially: stage the files for the first
group, commit, then move to the next. Rejected groups remain in the
working tree untouched.

## Step 2 — Draft the commit message

Analyze the changes to be committed and draft a message:

- **Subject line:** conventional commit prefix (`feat:`, `fix:`,
  `chore:`, `refactor:`, `docs:`, `test:`, `ci:`, `style:`,
  `perf:`, `build:`), under 72 characters total.
- **Body:** 1-2 sentences explaining *why* the change was made, not
  *what* changed. Hard-wrap at 72 characters. No bullet lists.
  Omit the body entirely when the subject line is self-explanatory
  — typo fixes, version bumps, and simple renames don't need a
  body restating the obvious.

If the user provided an argument hint (e.g., `/commit fix: handle
null input`), incorporate it into the subject line.

## Step 3 — Present or fast-path

**Fast-path:** If the user provided an explicit hint and the diff is
small, clearly matches the hint, and represents one obvious logical
change, skip conversational approval and go straight to staging and
committing.

Do not fast-path if there is any ambiguity about what should be
committed, if the repo is on `main` or `master`, if the repo is on
detached HEAD, if any sequencer sentinel exists, if there are mixed
staged and unstaged changes that need interpretation, or if any
secret-like files are involved.

The tool permission prompt already acts as a gate, so do not add a
second approval step when the fast-path is clearly safe.

**Standard path:** Otherwise, show the user:

1. The list of files that will be staged or committed.
2. The draft commit message.
3. Any branch mismatch or branch-ambiguity concern that needs the
   user's decision before committing.

Wait for the user to approve, request changes, or cancel.

## Step 4 — Stage and commit

- Stage specific files by name. Never use `git add -A` or `git add .`.
- Do not use interactive staging commands such as `git add -p`.
- Keep mutating steps as separate Bash invocations. Do not chain
  staging, committing, and verification into one opaque command.
- Commit using a HEREDOC to preserve formatting:

```bash
git commit -F - <<'EOF'
subject line here

Body text here, hard-wrapped at 72 characters.
EOF
```

## Step 5 — Verify

Run `git status` to confirm the commit succeeded.

Report the new commit hash and subject, and mention any remaining
unstaged changes that were intentionally left in the working tree.

## Safety rules

- Never commit files matching these patterns — they likely contain
  secrets: `.env*`, `*.key`, `*.pem`, `*.p12`, `*.pfx`, `id_rsa*`,
  `id_ed25519*`, `*credential*`, `*secret*`, `*.token`. Warn the
  user if they ask you to commit such files.
- Never use `--no-verify` or `--amend` unless the user explicitly
  asks.
- If a pre-commit hook fails, fix the issue, re-stage, and create a
  **new** commit. Never amend after a hook failure.
- If there are no changes to commit, say so and stop.
