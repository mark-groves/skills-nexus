# Provider workflows

Read only the section for the detected provider.

## GitHub

Use `gh` only for a GitHub remote.

Prerequisites:

```bash
gh --version
gh auth status
```

If authentication fails, ask the user to run `gh auth login`. Do not start an
interactive login.

Resolve the default branch when the remote-tracking symbolic ref is absent:

```bash
gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'
```

Check for an existing PR from the current branch:

```bash
gh pr view <current-branch> --json url --jq '.url'
```

A not-found result is expected and means creation may continue.

Create the PR while preserving its generated Markdown:

```bash
gh pr create --base "$base" --head "$current" --title "$title" --body-file - <<'EOF'
## Summary

- ...

## Validation

- ...
EOF
```

If creation fails, run the existing-PR check once. Return the URL if the PR was
created despite the error; otherwise report the original error and stop.

## Azure DevOps

Use the Azure CLI with the `azure-devops` extension only for an Azure Repos
remote. Azure DevOps may auto-detect the organization and project from the
current Git checkout; pass the repository explicitly.

Derive `repository` from the selected remote URL before running repository
commands. For HTTPS URLs containing `/_git/`, use the path segment after
`/_git/`. For Azure SSH `v3/<organization>/<project>/<repository>` URLs, use
the final path segment. Strip a trailing `.git`. If the repository name or ID
cannot be derived unambiguously, ask the user for it and stop rather than
querying an arbitrary repository.

Prerequisites:

```bash
az --version
az extension show --name azure-devops
az repos show --repository "$repository" --detect true --query id -o tsv
```

If `az` or the extension is absent, tell the user what to install; do not
install it automatically. If repository access fails, ask the user to
authenticate with `az login` or `az devops login --organization <url>`, or to
configure the correct organization/project. Do not request or expose a PAT.

Resolve the default branch when the remote-tracking symbolic ref is absent:

```bash
az repos show --repository "$repository" --detect true --query defaultBranch -o tsv
```

Strip `refs/heads/` from the result.

Check for an existing active PR from the current branch to the selected base:

```bash
az repos pr list \
  --detect true \
  --repository "$repository" \
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
  --detect true \
  --repository "$repository" \
  --source-branch "$current" \
  --target-branch "$base" \
  --title "$title" \
  --description "$body" \
  --query '[pullRequestId,repository.webUrl]' \
  -o tsv
```

Report `<repository-web-url>/pullrequest/<id>`. If creation fails, run the
existing-PR list command once before reporting the original error.
