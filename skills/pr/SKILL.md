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

Use a user-supplied branch argument as the PR target branch. Otherwise resolve
the repository default branch later; never silently assume `main`.

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

## 3. Resolve target and comparison branches

Track three distinct values:

- `default_branch`: the repository default branch name, used for publish-mode
  source-branch safety.
- `base`: the provider-facing PR target branch name. Use the user-supplied
  branch when present; otherwise use `default_branch`.
- `base_ref`: the locally available ref used by `git log` and `git diff`.
  Prefer the selected remote's tracking ref so comparisons do not depend on a
  stale or missing local branch.

First try the selected remote's symbolic default ref:

```bash
git symbolic-ref --quiet --short refs/remotes/<remote>/HEAD
```

Keep the full result, such as `upstream/main`, as the default comparison ref
and strip only the `<remote>/` prefix when setting `default_branch`.

In draft-only mode, never fall back to a provider CLI. If no base was supplied
and the remote symbolic ref is unavailable, ask the user for a locally
available base branch. A supplied base is sufficient for drafting, so
`default_branch` does not need to be resolved in this mode.

In publish mode, resolve `default_branch` even when the user supplied another
base, because it is required for source-branch safety. If the remote symbolic
ref is absent, use only the detected provider's default-branch command from
[provider workflows](references/providers.md). Stop if it cannot be resolved.

After selecting `base`, resolve `base_ref` without stripping remote context:

1. Use `<remote>/<base>` when `refs/remotes/<remote>/<base>` exists.
2. Otherwise use `<base>` when `refs/heads/<base>` exists locally.
3. Otherwise stop and ask the user to fetch the base or name a locally
   available ref; do not compare against a guessed branch.

When the remote symbolic default was selected as the base, reuse its full ref
as `base_ref`.

## 4. Validate the branch and provider

In publish mode, stop if the current branch is `main`, `master`, or the
resolved `default_branch`. Never push or create a PR from the default branch.
Draft-only mode may describe changes from any branch because it does not push
or create a PR.

Warn, but allow the user to continue, when the branch lacks a conventional
prefix such as `feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/`, or
`ci/`.

## 5. Gather the complete change

Inspect all branch work, not only the latest commit:

```bash
git log --oneline <base_ref>..HEAD
git diff --stat <base_ref>...HEAD
git diff <base_ref>...HEAD
```

Stop if there are no commits ahead of the base.

In publish mode, determine push state locally before provider authentication:

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

For publish mode, read [provider workflows](references/providers.md) and run
only the prerequisite checks for the detected provider after the local draft
and push state are known. A failed GitHub check is not evidence that an Azure
DevOps repository is misconfigured, or vice versa. If a prerequisite fails,
return the useful local draft, push state, and provider-specific remediation;
do not push or create a PR.

After prerequisites pass, use the provider workflow to check for an existing
active PR from this source branch to `base`. Return its web URL and stop if one
exists. Otherwise, do not stop to preview the title, body, file list, or push
command. Push when needed, then immediately use the provider-specific create
command. Preserve the generated Markdown exactly; do not flatten newlines or
rewrite it during submission.

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
