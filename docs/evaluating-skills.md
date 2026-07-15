# Evaluating skills

`scripts/eval_skills.py` measures whether a skill activates for the right tasks
and whether it improves observable outcomes in fresh Codex contexts.

Runtime packages and evidence are intentionally separate:

```text
skills/<name>/SKILL.md       instructions installed into an agent
evals/<name>/evals.json     repository-only trigger and behavior cases
evals/<name>/fixtures/      repository-only scenario inputs
```

Trigger cases exercise skill selection. Behavior cases run from identical
fixtures with and without the selected skill, then use a label-blinded judge to
compare both results against the same checks.

## Plan and run

Start with `--plan`. It validates selected cases and reports the number of agent
turns without invoking an agent:

```bash
python3 scripts/eval_skills.py --skill skill-architect --plan
```

Run every case for a skill:

```bash
python3 scripts/eval_skills.py --skill skill-architect
```

Run selected trigger and behavior cases:

```bash
python3 scripts/eval_skills.py \
  --skill skill-architect \
  --trigger-case 3 \
  --behavior-case 4
```

Useful controls include:

- `--suite trigger` or `--suite behavior` to run one evaluation type
- `--trigger-repeats` and `--behavior-repeats` to measure variance
- `--jobs` to limit concurrent agent turns
- `--model` and `--judge-model` to select task and grading models
- `--skill-universe isolated` to evaluate without repository peer skills
- `--fail-under <percent>` to enforce an absolute efficacy threshold

Run `python3 scripts/eval_skills.py --help` for the complete interface.

## Fixtures and isolation

Fixture references in `evals/<name>/evals.json` are relative to that eval
directory, normally `fixtures/<scenario>/...`. A scenario is copied into an
isolated workspace with the scenario prefix removed. An optional root
`setup.sh` can prepare deterministic inputs such as staged Git state. Fixture
scripts receive `EVAL_WORKSPACE` and `EVAL_SKILL_DIR` in a minimal environment
without inherited credentials.

The evaluator installs a clean runtime copy of the canonical skill. Repository
evidence cannot enter that copy because it lives outside the skill directory;
`working/`, Python caches, Git metadata, and runtime symlinks are also excluded
or rejected. By default, peer skills are available to both test conditions so
the comparison reflects normal deployment.

## Results

Runs are written to `.skill-evals/` by default:

- `results.json` contains structured results for automation and comparison.
- `report.md` provides a terminal- and Git-friendly review.
- `report.html` provides a self-contained visual report.
- `runs/` contains prompts, event traces, workspaces, and grader evidence.

Reports include skill and eval paths, runtime digests, activation, checks,
workspace changes, Git state, timing, token use, tool calls, baseline lift, and
confidence limitations. Missing or failed fixtures are reported as unknown
instead of being treated as successful.

Running evaluations requires an authenticated Codex CLI. The evaluator links
the existing Codex authentication file into a temporary isolated home and
removes that home after each turn.

Current runs compare skill versus baseline. Current-versus-candidate proving,
regression ingestion, and promotion gates are tracked in the
[roadmap](../ROADMAP.md).
