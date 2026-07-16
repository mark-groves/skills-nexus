---
name: pr
description: Draft pull request text or publish commands, or publish a pull request from the current Git branch on GitHub or Azure DevOps, including provider detection, safe push handling, a structured summary, and validation evidence. Use when the user asks to write, preview, create, open, submit, or publish a PR, including Azure Repos pull requests.
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

Treat requests to show or draft the exact publish commands without executing
them as **command-draft**. Inspect local state and read the detected provider
workflow so the commands are complete, but do not authenticate, push, or
create a PR.

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
- `git config --get "branch.<current-branch>.pushRemote"`
- `git config --get remote.pushDefault`
- `git config --get "branch.<current-branch>.remote"`

Read those three configuration keys exactly; do not rely on a case-sensitive
`--get-regexp` pattern to discover Git's case-insensitive `pushRemote` key.

Stop if HEAD is detached. If the working tree is dirty, suggest committing
first and stop unless the user explicitly asks to continue with the dirty tree.

Select `push_remote`, the destination for the current branch:

1. Prefer `branch.<current-branch>.pushRemote` when it names a configured
   remote.
2. Then prefer `remote.pushDefault` when it names a configured remote.
3. Then use the upstream remote when one exists.
4. Then prefer `branch.<current-branch>.remote` when it names a configured
   remote.
5. Then use the only configured remote.
6. If several remotes remain possible, ask the user to choose; do not assume
   `origin`.

Select `base_remote`, the repository that owns the PR target, independently:

1. If the user supplies `<remote>/<branch>` and `<remote>` is configured, use
   that remote and strip only the remote prefix when setting `base`.
2. Otherwise use a configured target remote explicitly named by the user. If
   the user names a repository URL or identifier that is not mapped to a
   configured remote, stop and ask them to add/select a target remote; do not
   invent a remote name or mutate Git configuration.
3. Otherwise prefer a configured remote named `upstream` when it differs from
   `push_remote`; this is the conventional target in a fork checkout.
4. Otherwise use the only configured remote.
5. Otherwise use `push_remote` only when it is the sole remote containing the
   requested base or the only remote with a symbolic default ref.
6. If several target remotes remain plausible, ask the user to choose. Do not
   reuse the push remote merely because the branch tracks it.

This separation is required in fork workflows: a branch may push to `origin`
while its PR targets `upstream/main`.

Read `push_fetch_url` with `git remote get-url <push_remote>`, the actual push
destination as `push_url` with `git remote get-url --push <push_remote>`, and
the target fetch URL as `base_url` with
`git remote get-url <base_remote>`. Keep `push_fetch_url` and `push_url`
distinct. A configured `pushurl` overrides the fetch URL for transport,
provider-source derivation, and host compatibility checks. In command-draft
mode, label both values before the commands. Detect the PR provider from
`base_url`, preferring an explicit provider named by the user:

- GitHub: `github.com`, a host beginning with `github.`, or a host already
  configured for GitHub CLI
- Azure DevOps: `dev.azure.com`, `ssh.dev.azure.com`,
  `vs-ssh.visualstudio.com`, or an organization host ending in
  `.visualstudio.com`

For an otherwise unfamiliar host in publish mode, `gh auth status --hostname
<host>` may be used as a provider probe: a host configured for GitHub CLI is a
GitHub Enterprise host. Do not interpret an arbitrary unknown host as GitHub.
Non-publish modes may continue only when the provider is explicit or locally
recognizable. Otherwise ask which provider and publishing tool to use.

Stop if the push and base remotes resolve to incompatible providers or hosts.
GitHub fork PRs must remain on one GitHub host. Azure Repos PRs must use the
same organization, project, and repository for source and target branches.

## 3. Resolve target and comparison branches

Track three distinct values:

- `default_branch`: the repository default branch name, used for publish-mode
  source-branch safety.
- `base`: the provider-facing PR target branch name. Use the user-supplied
  branch when present; otherwise use `default_branch`.
- `base_ref`: the locally available ref used by `git log` and `git diff`.
  Prefer `base_remote`'s tracking ref so comparisons do not depend on a
  stale or missing local branch.

First try the selected remote's symbolic default ref:

```bash
git symbolic-ref --quiet --short refs/remotes/<base_remote>/HEAD
```

Keep the full result, such as `upstream/main`, as the default comparison ref
and strip only the `<remote>/` prefix when setting `default_branch`.

In draft-only and command-draft modes, never fall back to a provider CLI. If no
base was supplied and the remote symbolic ref is unavailable, ask the user for
a locally available base branch. A supplied base is sufficient for drafting,
so `default_branch` does not need to be resolved in these modes.

In publish mode, resolve `default_branch` even when the user supplied another
base, because it is required for source-branch safety. If the remote symbolic
ref is absent, use only the detected provider's default-branch command from
[provider workflows](references/providers.md). Stop if it cannot be resolved.

After selecting `base`, resolve `base_ref` without stripping remote context:

1. Use `<base_remote>/<base>` when
   `refs/remotes/<base_remote>/<base>` exists.
2. Otherwise use `<base>` when `refs/heads/<base>` exists locally.
3. Otherwise stop and ask the user to fetch the base or name a locally
   available ref; do not compare against a guessed branch.

When the remote symbolic default was selected as the base, reuse its full ref
as `base_ref`.

## 4. Validate the branch and provider

In publish mode, stop if the current branch is `main`, `master`, or the
resolved `default_branch`. Never push or create a PR from the default branch.
Draft-only and command-draft modes may inspect changes from any branch because
they do not push or create a PR.

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

In publish and command-draft modes, determine push state locally before any
provider authentication. Compare against
`refs/remotes/<push_remote>/<current-branch>` when it exists; do not use a
tracking branch from a different remote as evidence that the push destination
is current:

- No upstream: push with `git push -u <push_remote> <current-branch>`.
- A push-remote tracking ref exists and local is ahead: push with
  `git push <push_remote> <current-branch>`.
- The push-remote tracking ref is current: no push is needed.
- The push-remote tracking ref is ahead or diverged: stop and ask the user to
  reconcile it.
- An upstream exists on another remote but no push-remote tracking ref exists:
  push with `git push <push_remote> <current-branch>` without changing the
  branch's upstream.

Use `git rev-list --left-right --count
refs/remotes/<push_remote>/<current-branch>...HEAD` for ahead/behind counts.

Prevent Git transport from opening an interactive credential prompt. Inspect
`push_url`, not the remote's fetch URL, and use the matching non-interactive
form for both the preflight and eventual push:

- SSH: set
  `GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes'`.
- HTTPS: set `GCM_INTERACTIVE=Never GIT_TERMINAL_PROMPT=0`.

In publish mode, run `git ls-remote <push_url> HEAD` with that
environment before any push. Stop on failure; do not fall through to an
interactive password, key-passphrase, or host-key prompt. Use the same
environment on `git push`. In command-draft mode, include the appropriate
environment in the returned preflight and push commands without running them.

For an SSH failure, report that provider CLI authentication does not
authenticate Git transport. Suggest checking loaded keys with `ssh-add -l`,
loading the intended key into `ssh-agent`, and verifying an unknown host key
fingerprint out of band. Do not run `ssh-add`, accept a host key, change the
remote URL, or weaken host-key checking automatically. For HTTPS, recommend
the provider-supported credential manager or token flow without requesting a
secret in chat.

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

For command-draft mode, read only the detected provider section in
[provider workflows](references/providers.md) and return the exact ordered
duplicate-check, push, and create commands with all derived remote, repository,
branch, organization, and project values filled in. Clearly label them as not
executed. For an SSH remote, also state that provider CLI authentication does
not authenticate Git transport and that a failed batch-mode preflight requires
the correct key to be loaded in `ssh-agent`. Do not run provider authentication
or any mutating command.

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
push result. Report `base` as the branch-only provider target (for example,
`main`), never as `<base_remote>/<base>`. If local comparison context is useful,
label the remote-tracking value separately as `base_ref`.

## Safety

- Never force push or use `--no-verify`.
- Never allow Git to prompt interactively for remote credentials during this
  workflow.
- Never push the default branch.
- Never create a duplicate PR.
- Never install a CLI or extension, start interactive authentication, or alter
  provider defaults without the user's approval.
- If creation reports an error, perform the provider workflow's one read-back
  check. Do not retry creation automatically.
