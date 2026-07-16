# Provider workflows

Read only the section for the detected provider.

## GitHub

Use `gh` only for GitHub remotes, including GitHub Enterprise hosts configured
for GitHub CLI.

Derive these values locally before running repository-scoped commands:

- `github_host` from `base_remote`.
- `github_target_repository` as `[HOST/]OWNER/REPO` from `base_remote`.
- `github_source_repository` and `github_source_owner` from `push_remote`.

Normalize HTTPS, SCP-style SSH, and `ssh://` URLs, and strip a trailing `.git`.
For example, `git@github.com:acme/widget.git` becomes
`github.com/acme/widget`. Stop if any host, owner, or repository is ambiguous,
if a derived owner or repository contains characters outside GitHub slug
syntax, or if source and target use different hosts.

Bind every repository-scoped command to `github_target_repository`. Pass it as
the positional repository to `gh repo view` and with `--repo` to every `gh pr`
command. Do not let `gh` infer a repository from the current directory.

Prerequisites:

```bash
gh --version
gh auth status --hostname "$github_host"
```

If authentication fails, ask the user to run
`gh auth login --hostname "$github_host"`. Do not start an interactive login.

Resolve the default branch when the remote-tracking symbolic ref is absent:

```bash
gh repo view "$github_target_repository" \
  --json defaultBranchRef \
  --jq '.defaultBranchRef.name'
```

Check for an existing open PR from the current branch to the selected base.
Both filters are required because one source branch may have PRs targeting
different bases:

```bash
gh pr list \
  --repo "$github_target_repository" \
  --head "$current" \
  --base "$base" \
  --state open \
  --json url,headRepositoryOwner \
  --jq "[.[] | select(.headRepositoryOwner.login == \"$github_source_owner\") | .url][0] // empty"
```

A not-found result is expected and means creation may continue.

For a same-repository PR, set `github_head` to `$current`. For a fork PR, set
it to `$github_source_owner:$current` so GitHub selects the source fork rather
than a same-named target branch.

Create the PR while preserving its generated Markdown:

```bash
gh pr create \
  --repo "$github_target_repository" \
  --base "$base" \
  --head "$github_head" \
  --title "$title" \
  --body-file - <<'EOF'
## Summary

- ...

## Validation

- ...
EOF
```

If creation fails, run the same target-repository, head-branch, base-branch,
and source-owner-filtered existing PR check once. Return the URL if the PR was
created despite the error; otherwise report the original error and stop.

## Azure DevOps

Use the Azure CLI with the `azure-devops` extension only for an Azure Repos
remote.

Derive `azure_organization`, `azure_project`, and `azure_repository` from the
`base_remote` URL before running repository commands. For
`https://dev.azure.com/<organization>/<project>/_git/<repository>`, construct
the organization URL as `https://dev.azure.com/<organization>`. For Azure SSH
`v3/<organization>/<project>/<repository>` URLs, derive the same values from
the three path components. Handle `*.visualstudio.com` organization URLs and
strip a trailing `.git`. URL-decode path segments before passing them to Azure
CLI. Stop if any value is ambiguous.

Derive the corresponding values from `push_remote` and require them to match;
Azure Repos does not create cross-repository PRs. Pass organization, project,
and repository explicitly to every `az repos` command rather than relying on
checkout or CLI defaults.

Azure CLI authentication and Git remote authentication are separate. For an
SSH push URL such as `git@ssh.dev.azure.com:v3/...`, require the core
workflow's batch-mode SSH preflight before pushing. If it fails, explain that
the SSH key must be registered with Azure DevOps and loaded into `ssh-agent`;
do not prompt for a passphrase or treat successful `az login` as Git access.

Prerequisites:

```bash
az --version
az extension show --name azure-devops
az repos show \
  --organization "$azure_organization" \
  --project "$azure_project" \
  --repository "$azure_repository" \
  --query id \
  -o tsv
```

If `az` or the extension is absent, tell the user what to install and include
the exact fully scoped `az repos show` access check to run afterward; do not
install anything automatically. If repository access fails, ask the user to
authenticate with `az login` or
`az devops login --organization "$azure_organization"`. Do not request or
expose a PAT.

Resolve the default branch when the remote-tracking symbolic ref is absent:

```bash
az repos show \
  --organization "$azure_organization" \
  --project "$azure_project" \
  --repository "$azure_repository" \
  --query defaultBranch \
  -o tsv
```

Strip `refs/heads/` from the result.

Check for an existing active PR from the current branch to the selected base:

```bash
az repos pr list \
  --organization "$azure_organization" \
  --project "$azure_project" \
  --repository "$azure_repository" \
  --source-branch "$current" \
  --target-branch "$base" \
  --status active \
  --query '[0].[pullRequestId,repository.webUrl]' \
  -o tsv
```

When this returns an ID and repository web URL, report
`<repository-web-url>/pullrequest/<id>` and stop.

Create the PR. Use a shell variable so multiline Markdown reaches Azure DevOps
unchanged:

```bash
body=$(cat <<'EOF'
## Summary

- ...

## Validation

- ...
EOF
)
az repos pr create \
  --organization "$azure_organization" \
  --project "$azure_project" \
  --repository "$azure_repository" \
  --source-branch "$current" \
  --target-branch "$base" \
  --title "$title" \
  --description "$body" \
  --query '[pullRequestId,repository.webUrl]' \
  -o tsv
```

Report `<repository-web-url>/pullrequest/<id>`. If creation fails, run the
existing-PR list command once before reporting the original error.
