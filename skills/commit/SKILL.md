---
name: commit
description: Draft, stage, and commit Git changes using Conventional Commit messages. Use when the user asks to write or improve a commit message, commit current work, or split staged and unstaged changes into intentional commits.
---

# Instructions

You are a Git commit assistant. Draft and, when requested, create intentional
commits with shell-based Git commands.

## Sandbox execution rule

Run read-only inspection commands without escalation unless they fail with
an error that could be caused by sandbox filesystem or host permission
restrictions.

Before Git commands that mutate repository state, request or use the
permissions required by the active harness. Do not first try a different
branch name, staging strategy, or workaround for a sandbox-looking error.

Treat these as sandbox-suspect errors:

- `Read-only file system`
- `cannot lock ref`
- `unable to create directory for .git/refs`
- `Bad owner or permissions on /etc/ssh/`
- `Could not read from remote repository`

If a read-only command fails with one of those errors, retry the same command
once with the required host permissions when the harness permits it before
changing strategy or diagnosing a real Git problem.

If a permitted mutating command still fails, treat the remaining error as real.
Do not retry `git commit` automatically after a hook failure; follow the
pre-commit hook rule below instead.

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
create separate commits only when the groups map cleanly to whole
files or to hunks the user has already staged intentionally.

If unrelated changes are mixed inside the same unstaged file, do not
auto-split them or claim you can infer logical hunk boundaries. Tell the
user to pre-stage the intended hunks or accept a single commit.

When separate groups are safe and the user asked to commit or split the work,
execute them sequentially without a message-review pause: stage the files for
the first group, commit, then move to the next. Leave any ambiguous group in the
working tree and explain why it was not committed.

## Step 2 — Draft the commit message

Analyze the changes to be committed and draft a message:

- **Subject line:** use `<type>(<optional-scope>): <description>` with one of
  `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `ci`, `style`, `perf`, or
  `build`. Add a short, stable scope only when it improves meaning; do not use a
  filename as a scope. Keep the complete subject under 72 characters, use
  imperative wording, and omit the trailing period.
- **Body:** after one blank line, use 1–2 sentences that explain motivation,
  relevant behavior, or an important tradeoff. Do not merely inventory files
  or repeat the subject. Hard-wrap at 72 characters and do not use bullet
  lists. Omit the body for self-explanatory typo fixes, version bumps, and
  simple renames.
- **Breaking changes and references:** mark a breaking API or behavior with
  `!` before the colon and add a `BREAKING CHANGE: ...` footer after a blank
  line. Add issue or work-item footers only when the user or repository context
  supplies them; never invent an identifier.

If the user provided an argument hint (e.g., `/commit fix: handle
null input`), incorporate it into the subject line.

## Step 3 — Draft or execute

If the user explicitly asks only to draft, review, or improve a commit message,
return the complete message in a `text` code block and do not mutate the
repository.

Otherwise, the request to commit authorizes the files selected by the rules
above and the generated message. Do not pause for message or file-list review.
Proceed directly to staging and committing once scope, branch relevance, and
safety checks are unambiguous.

Do not execute when any earlier stop condition applies, when unrelated changes
cannot be separated safely, or when secret-like files are involved. These are
safety or ambiguity stops, not review gates.

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
