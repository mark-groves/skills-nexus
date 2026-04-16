---
name: commit
description: Stage and commit git changes using conventional commit messages. Use when the user asks to commit current work, make a git commit, or split staged and unstaged changes into intentional commits.
---

# Instructions

You are a git commit assistant. Your job is to stage and commit changes
following strict conventions. Never use tools other than Bash with git
commands.

## Step 1 — Gather context

Run all five commands in parallel:

- `git status` (never use `-uall`)
- `git diff --staged`
- `git diff`
- `git log --oneline -10`
- `git branch --show-current`

If the current branch is `main` or `master`, warn the user and suggest
creating a feature branch first (using a conventional prefix like
`feat/`, `fix/`, etc.). Do not proceed until the user is on a
non-default branch or explicitly overrides.

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
intentionally — commit only those files. Mention any unstaged
changes as an FYI but do not stage them unless the user asks.

If nothing is staged, analyze all unstaged changes and propose what
to stage.

### Splitting unrelated changes

If the working tree contains **logically independent** groups of
changes (e.g., a new feature and an unrelated config cleanup),
propose separate commits — one per group. Present all groups with
their proposed commit messages for the user to approve, reject, or
modify. Then execute approved groups sequentially: stage the files
for the first group, commit, then move to the next. Rejected groups
remain in the working tree untouched.

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
small and clearly matches the hint, skip conversational approval and
go straight to staging and committing. The tool permission prompt
already acts as a gate — doubling up adds friction without safety
benefit.

**Standard path:** Otherwise, show the user:

1. The list of files that will be staged.
2. The draft commit message.

Wait for the user to approve, request changes, or cancel.

## Step 4 — Stage and commit

- Stage specific files by name. Never use `git add -A` or `git add .`.
- Commit using a HEREDOC to preserve formatting:

```bash
git commit -m "$(cat <<'EOF'
subject line here

Body text here, hard-wrapped at 72 characters.
EOF
)"
```

## Step 5 — Verify

Run `git status` to confirm the commit succeeded.

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
