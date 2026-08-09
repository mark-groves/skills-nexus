# Cloud Agent ops

Cursor Cloud Agents operate this repository as a skill foundry. They propose
skill improvements on branches and open pull requests. They do not rewrite
installed plugins in place, merge to the default branch, or treat their own
diagnosis as proof.

This guide is the operator playbook for that loop. The evidence contract lives
in [continuous improvement](continuous-improvement.md) and
[capability optimisation](capability-optimisation.md).

## Role

| Actor | Owns |
| --- | --- |
| Cloud Agent | Branch work, local checks, PR with reproduction notes |
| Human reviewer | Merge decision, permission or instruction changes |
| Repository CI | `check-skills.sh`, quality jobs, dependency review |
| Cursor local plugins | Runtime copies under `~/.cursor/plugins/local/` |

Canonical sources stay in `plugins/<bundle>/`. Evals, fixtures, and raw
observations stay outside the plugin package and must never ship with a
deployed copy.

## Improve a skill

1. Start from current `main`. Create a focused branch
   (`fix/<skill>-...` or `feat/<skill>-...`).
2. Edit only the owning bundle under `plugins/<bundle>/skills/<name>/`. Keep
   companion skills in the same plugin when the change is shared behavior
   (`commit`/`pr`, `cloud-diagram`/`drawio-shapes`).
3. If the change needs a regression, add the smallest redacted fixture under
   `evals/<name>/`. Do not commit `.skill-feedback/` or full transcripts.
4. Prove the repository contract still holds:

   ```bash
   bash scripts/check-skills.sh
   ```

   Prefer `bash scripts/check-quality.sh` when scripts, workflows, or Python
   tooling changed.
5. Preview eval or CapOpt plans when relevant (`--plan` needs no live harness).
   Live Codex matrices are optional and demoted; do not block a PR on them.
6. Open a pull request. Summarize the failure or hypothesis, the files touched,
   the checks run, and residual risk. Leave merge to a human.

Never promote by editing a user's `~/.cursor/plugins/local/` copy and calling
that done. Refresh local installs only after the change lands on `main`.

## What stays out of PRs

- Raw observations, chat transcripts, or secrets
- Eval expected answers copied into `SKILL.md`
- Whole-repo rewrites that turn every skill into one plugin
- Automatic merge, force-push to `main`, or skipping hooks

## Local Cursor proof after merge

After a plugin change merges, refresh the local Cursor install with a real
directory copy. Cursor loads Agent Plugins from
`~/.cursor/plugins/local/<name>/` when `plugin.json` sits at the plugin root.

```bash
mkdir -p ~/.cursor/plugins/local
rsync -a --delete "$PWD/plugins/git-workflow/" ~/.cursor/plugins/local/git-workflow/
rsync -a --delete "$PWD/plugins/drawio/" ~/.cursor/plugins/local/drawio/
rsync -a --delete "$PWD/plugins/skill-architect/" ~/.cursor/plugins/local/skill-architect/
```

Reload the Cursor window. Confirm load in the Cursor Plugins log
(`loadUserLocalPlugin <name> loaded`) or under Customize → Plugins. External
symlinks into the repo are often rejected; prefer `rsync` for local proof.

Harness skill-root installs remain available for non-plugin targets via
`bash scripts/deploy-skills.sh --harness <target> --skill <name>`. See
[deployment](deployment.md).

## Failure handling

| Symptom | Action |
| --- | --- |
| `check-skills.sh` fails | Fix before opening or updating the PR |
| Local plugin missing after copy | Confirm path is `~/.cursor/plugins/local/<name>/plugin.json`, then reload |
| Symlink install silent no-op | Replace with `rsync`; check logs for `symlink target ... is outside` |
| Suspected skill bug without fixture | File an observation draft or open a draft PR with a minimal repro; do not widen scope |
| CapOpt or live eval unavailable | Keep the PR on static proof and human review; note the missing evidence |

## Related guides

- [Authoring skills](authoring-skills.md)
- [Deployment](deployment.md)
- [Continuous improvement](continuous-improvement.md)
- [Development and CI](development.md)
- [Roadmap](../ROADMAP.md)
