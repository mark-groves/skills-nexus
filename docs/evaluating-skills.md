# Evaluating skills

`scripts/eval_skills.py` measures whether a skill activates for the right tasks
and whether it improves observable task outcomes in fresh Codex contexts.

An evaluation definition lives at `evals/evals.json` inside a skill. Trigger
cases exercise skill selection. Behavior cases run from identical fixtures with
and without the selected skill, then use a label-blinded judge to compare both
results against the same checks.

## Plan a run

Start with `--plan`. It validates the selected cases and reports the number of
agent turns without invoking an agent:

```bash
python3 scripts/eval_skills.py --skill skill-architect --plan
```

Skills can be selected by unique short name, full skill ID, or directory.

## Run evaluations

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

Behavior fixtures live under `evals/fixtures/<scenario>/`. Their contents are
copied into an isolated workspace with the scenario directory prefix removed.
An optional root `setup.sh` can prepare deterministic inputs such as staged Git
state. Fixture scripts receive `EVAL_WORKSPACE` and `EVAL_SKILL_DIR` in a
minimal environment without inherited credentials.

The selected skill is sanitized before installation and its `evals/` directory
is removed from the task copy. This keeps expected results out of the context.
By default, the repository's other deployable skills are available to both test
conditions so the comparison reflects normal deployment.

## Results

Runs are written to `.skill-evals/` by default:

- `results.json` contains structured results for automation and comparison.
- `report.md` provides a terminal- and Git-friendly review.
- `report.html` provides a self-contained visual report.
- `runs/` contains prompts, event traces, workspaces, and grader evidence.

Reports include activation, checks, workspace changes, Git state, timing, token
use, tool calls, baseline lift, and confidence limitations. Missing or failed
fixtures are reported as unknown instead of being treated as successful.

Running evaluations requires an authenticated Codex CLI. The evaluator links
the existing Codex authentication file into a temporary isolated home and
removes that home after each turn.
