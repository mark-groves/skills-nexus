# Deployment

For normal installation from GitHub, use the community `skills` CLI. It
discovers the canonical packages under `skills/<name>/`:

```bash
npx skills add mark-groves/skills-nexus --list
npx skills add mark-groves/skills-nexus --skill commit --agent codex
```

The repository's deployment script is a local-development and controlled-copy
adapter. Run it from any directory; it resolves canonical skill paths from the
checkout and target paths from `harnesses/<name>.json`.

## Select a harness and skills

Every command requires `--harness`:

| Harness | User destination | Project destination |
| --- | --- | --- |
| `agents` | `~/.agents/skills` | `.agents/skills` |
| `claude-code` | `~/.claude/skills` | `.claude/skills` |
| `codex` | `~/.agents/skills` | `.agents/skills` |
| `copilot` | `~/.copilot/skills` | `.github/skills` |
| `cursor` | `~/.cursor/skills` | `.cursor/skills` |
| `kiro` | `~/.kiro/skills` | `.kiro/skills` |

Select one or more canonical names with repeated `--skill` options, or use
`--all`:

```bash
bash scripts/deploy-skills.sh \
  --harness cursor \
  --skill commit \
  --skill pr

bash scripts/deploy-skills.sh --harness agents --all
```

`skills/<name>` is also accepted as an explicit selector. Harness-specific
metadata and install locations are adapter concerns; there are no separate
harness-owned copies of the skill source.

## Choose a scope

User scope is the default:

```bash
bash scripts/deploy-skills.sh --harness claude-code --skill commit
```

Project scope installs beneath the project root:

```bash
bash scripts/deploy-skills.sh \
  --harness copilot \
  --skill pr \
  --scope project \
  --project-root /path/to/project
```

Every deployment installs a clean runtime copy of the canonical directory
without repo-only working files. Evals and raw observations live outside
`skills/`, so neither can leak into an installed copy. The packager preserves
`SKILL.md` exactly; deployment never rewrites metadata for a target.

Redeployment replaces an existing destination directory. A destination that is
an old symlink is removed and replaced with a directory without modifying the
symlink target. An existing non-directory path blocks deployment.

## Preview operations

Use `--dry-run` to inspect target paths and operations without changing them:

```bash
bash scripts/deploy-skills.sh \
  --harness agents \
  --all \
  --dry-run
```

Run `bash scripts/deploy-skills.sh --help` for the complete command reference.
