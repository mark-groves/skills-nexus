# Deployment

The deployment script installs skill directories into the location discovered
by a selected agent harness. Run it from any directory; paths are resolved from
the repository checkout.

## Select a harness and skills

Every command requires `--harness`. The name selects a manifest from
`harnesses/<name>.json`:

| Harness | User destination | Project destination |
| --- | --- | --- |
| `agents` | `~/.agents/skills` | `.agents/skills` |
| `claude-code` | `~/.claude/skills` | `.claude/skills` |
| `codex` | `~/.codex/skills` | `.codex/skills` |
| `copilot` | `~/.copilot/skills` | `.github/skills` |
| `cursor` | `~/.cursor/skills` | `.cursor/skills` |
| `kiro` | `~/.kiro/skills` | `.kiro/skills` |

Select one or more skills with repeated `--skill` options:

```bash
bash scripts/deploy-skills.sh \
  --harness cursor \
  --skill commit \
  --skill pr
```

A short folder name works when it is unique. A full skill ID is also accepted,
such as `portable/pr` or `harness/codex/example`.

Bulk selectors are available when maintaining a complete installation:

- `--all-portable` selects every portable skill.
- `--all-for-harness` selects every skill specific to the chosen harness.
- `--all` combines both groups.

Harness-specific selections must match the harness named by `--harness`.

## Choose a scope

User scope is the default and installs into the manifest's user destination:

```bash
bash scripts/deploy-skills.sh --harness claude-code --skill commit
```

Project scope installs beneath a project root:

```bash
bash scripts/deploy-skills.sh \
  --harness copilot \
  --skill portable/pr \
  --scope project \
  --project-root /path/to/project
```

When `--project-root` is omitted, project scope uses the current working
directory.

## Choose an install mode

The script supports `--mode symlink` and `--mode copy`.

| Installation | Default | Update behavior |
| --- | --- | --- |
| User scope, most harnesses | `symlink` | Changes in the checkout are immediately visible |
| User scope, Codex | `copy` | Run deployment again to refresh the installed copy |
| Project scope | `copy` | Run deployment again to refresh the project copy |

Copy mode replaces an existing destination directory for the selected skill.
Symlink mode replaces an existing symlink, while an existing regular directory
is preserved and reported as skipped.

Codex copy deployment filters the installed `SKILL.md` frontmatter to fields
the Codex runtime can load safely. The canonical skill in this repository is
left unchanged.

## Preview and inspect options

Add `--dry-run` to print the target directory and file operations without
changing the installation:

```bash
bash scripts/deploy-skills.sh \
  --harness agents \
  --all-portable \
  --dry-run
```

The complete command reference is available from the script:

```bash
bash scripts/deploy-skills.sh --help
```
