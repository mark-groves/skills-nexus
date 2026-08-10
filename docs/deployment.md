# Deployment

Skills Nexus publishes companion skills as [Agent Plugins](https://agent-plugins.org/)
under `plugins/<bundle>/`. Each plugin has a root `plugin.json` and one or more
skills under `skills/<name>/`.

## Cursor Agent Plugins (primary)

Copy each plugin into `~/.cursor/plugins/local/`. Use a real directory, not a
symlink into the repo. Cursor rejects those external symlink targets.

```bash
mkdir -p ~/.cursor/plugins/local
rsync -a --delete "$PWD/plugins/git-workflow/" ~/.cursor/plugins/local/git-workflow/
rsync -a --delete "$PWD/plugins/drawio/" ~/.cursor/plugins/local/drawio/
rsync -a --delete "$PWD/plugins/skill-architect/" ~/.cursor/plugins/local/skill-architect/
```

Reload the Cursor window. Check Customize → Plugins, or the Cursor Plugins log
for `loadUserLocalPlugin <name> loaded`. `git-workflow` loads `commit` and
`pr`; `drawio` loads `cloud-diagram` and `drawio-shapes`.

## Local harness skill-root helper

`scripts/deploy-skills.sh` remains available for development installs into
harness skill directories. It resolves canonical skill paths from plugin bundles
and target paths from `harnesses/<name>.json`. Selecting a skill expands to the
full owning companion bundle before copying.

Every command requires `--harness`:

| Harness | User destination | Project destination |
| --- | --- | --- |
| `agents` | `~/.agents/skills` | `.agents/skills` |
| `claude-code` | `~/.claude/skills` | `.claude/skills` |
| `codex` | `~/.agents/skills` | `.agents/skills` |
| `copilot` | `~/.copilot/skills` | `.github/skills` |
| `cursor` | `~/.cursor/skills` | `.cursor/skills` |
| `kiro` | `~/.kiro/skills` | `.kiro/skills` |

```bash
bash scripts/deploy-skills.sh \
  --harness cursor \
  --skill commit

bash scripts/deploy-skills.sh --harness agents --all
```

`--skill commit` installs both `commit` and `pr`. Bundle paths such as
`plugins/git-workflow/skills/commit` are also accepted as selectors.
Harness-specific metadata and install locations are adapter concerns; there are
no separate harness-owned copies of the skill source.

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

Every deployment installs clean runtime copies of the selected bundle members
without repo-only working files. Evals and raw observations live outside
`plugins/`, so neither can leak into an installed copy. The packager preserves
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
