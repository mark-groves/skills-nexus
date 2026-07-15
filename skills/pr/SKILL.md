---
name: pr
description: Draft or publish a pull request from the current Git branch on GitHub or Azure DevOps, including provider detection, safe push handling, a structured summary, and validation evidence. Use when the user asks to write, create, open, submit, or publish a PR, including Azure Repos pull requests.
---

# Pull request workflow

Draft and, when requested, publish a pull request without assuming every Git
remote is hosted on GitHub.

Use shell commands with `git` and the detected provider CLI. Run read-only
local inspection first. Request the permissions required by the active harness
before commands that use network credentials or mutate repository state. Do
not change remotes, branches, or command strategy merely to work around a
permission error.

## 1. Determine the requested mode

Treat requests to write, format, or preview PR text as **draft-only**. Do not
push, authenticate to a provider, or create a PR in this mode.

Treat requests to create, open, submit, or publish a PR as **publish**. The
request authorizes the required branch push and PR creation after all safety,
provider, and repository checks pass; do not pause for draft approval.

Use a user-supplied branch argument as the base branch. Otherwise resolve the
default branch later; never silently assume `main`.

## 2. Inspect local state

Minimize tool calls. Gather these in one read-only shell invocation when
possible:

- `git status --short --branch` (never use `-uall`)
- `git symbolic-ref --quiet --short HEAD`
- `git remote -v`
- `git rev-parse --abbrev-ref @{upstream}` (failure means no upstream)

Stop if HEAD is detached. If the working tree is dirty, suggest committing
first and stop unless the user explicitly asks to continue with the dirty tree.

Select the remote that represents the branch's publish destination:

1. Use the upstream remote when one exists.
2. Otherwise prefer `branch.<current-branch>.pushRemote`.
3. Then prefer `remote.pushDefault`.
4. Then prefer `branch.<current-branch>.remote`.
5. Then use the only configured remote.
6. If several remotes remain possible, ask the user to choose; do not assume
   `origin`.

Read its URL with `git remote get-url <remote>`. Prefer an explicit provider
named by the user; otherwise detect it from the URL:

- GitHub: `github.com`
- Azure DevOps: `dev.azure.com`, `ssh.dev.azure.com`,
  `vs-ssh.visualstudio.com`, or an organization host ending in
  `.visualstudio.com`

Do not interpret an unfamiliar host as GitHub. Draft-only mode may continue if
the base can be resolved locally. Publish mode must stop and ask which provider
and publishing tool to use.

## 3. Resolve the base branch

First try the selected remote's symbolic default:

```bash
git symbolic-ref --quiet --short refs/remotes/<remote>/HEAD
```

Strip the `<remote>/` prefix. If that fails, use the detected provider's
default-branch command from [provider workflows](references/providers.md).
Stop and ask for a base branch if neither method succeeds.

Even when the user supplied a different base, still resolve the default branch
for source-branch safety checks.

## 4. Validate the branch and provider

Stop if the current branch is `main`, `master`, or the resolved default branch.
Never push or create a PR from the default branch.

Warn, but allow the user to continue, when the branch lacks a conventional
prefix such as `feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/`, or
`ci/`.

For publish mode, read
[provider workflows](references/providers.md) and run only the prerequisite
checks for the detected provider. A failed GitHub check is not evidence that an
Azure DevOps repository is misconfigured, or vice versa.

## 5. Gather the complete change

Inspect all branch work, not only the latest commit:

```bash
git log --oneline <base>..HEAD
git diff --stat <base>...HEAD
git diff <base>...HEAD
```

Stop if there are no commits ahead of the base.

In publish mode, use the provider workflow to check for an existing active PR
from this source branch to the selected base. Return its web URL and stop if one
exists.

Determine push state:

- No upstream: push with `git push -u <remote> <current-branch>`.
- Upstream exists and local is ahead: push with `git push`.
- Upstream is current: no push is needed.
- Upstream is ahead or diverged: stop and ask the user to reconcile it.

Use `git rev-list --left-right --count @{upstream}...HEAD` for ahead/behind
counts.

## 6. Draft the PR

Write a title under 70 characters. Use imperative wording with no trailing
period. Use a Conventional Commit-style prefix and optional stable scope only
when the change maps cleanly to one, for example
`feat(pr): support Azure DevOps repositories`; otherwise use a plain imperative
title.

Write concise Markdown based on the diff and observed validation:

```markdown
## Summary

- <primary outcome and why it matters>
- <important behavioral or operational impact, when distinct>

## Validation

- `<exact command>` — passed
- Not run: <specific reason>

## Notes

- <breaking change, migration, rollout risk, or follow-up>
```

Apply these formatting rules:

- Keep Summary to 1–3 outcome-focused bullets; do not inventory files or repeat
  the title.
- Report only validation that evidence shows was run. Include the result, not
  merely a proposed test plan.
- Use `Not run: <reason>` when no validation ran.
- Omit Notes entirely when there is no material note. Never emit empty sections
  or placeholder text.
- Mention breaking changes, migrations, and user-visible impact explicitly.

## 7. Return or publish

For draft-only mode, return the provider (if known), base/head branches, title,
and body. Do not publish it.

For publish mode, do not stop to preview the title, body, file list, or push
command. Push when needed, then immediately use the provider-specific create
command from [provider workflows](references/providers.md). Preserve the
generated Markdown exactly; do not flatten newlines or rewrite it during
submission.

Return the human-facing PR URL, provider, base/head branches, title, body, and
push result.

## Safety

- Never force push or use `--no-verify`.
- Never push the default branch.
- Never create a duplicate PR.
- Never install a CLI or extension, start interactive authentication, or alter
  provider defaults without the user's approval.
- If creation reports an error, perform the provider workflow's one read-back
  check. Do not retry creation automatically.
