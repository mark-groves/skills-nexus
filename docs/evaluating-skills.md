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

Candidate mode adds a third fresh condition without changing the default
current-versus-baseline path:

```bash
python3 scripts/eval_skills.py \
  --skill skill-architect \
  --candidate /path/to/candidate-skill
```

`--candidate` accepts an absolute directory or a path relative to
`--repo-root`. The directory may have any working name, but its canonical
frontmatter `name` must match the selected skill. Before any agent turn, the
evaluator verifies the minimal publishable metadata contract, rejects runtime
symlinks, and creates a clean runtime copy.

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

In candidate mode, Baseline, Current, and Candidate each run in a fresh context
from the same fixture template. Current and Candidate are installed separately
under the selected skill's logical discovery name, even when the candidate
source directory has a different working name. Repository peer skills are
copied identically into all three conditions and the candidate source is never
also installed as a peer.

Current and Candidate trigger cases run independently because their
descriptions may differ. For behavior grading, one structured judge turn sees
all three evidence bundles under deterministic randomized labels such as `A`,
`B`, and `C`; condition identities and runtime instructions are withheld. One
judge turn costs less than three separately blinded pairwise turns and applies
one grading standard to every output, while the shared turn means the grades
are not statistically independent. Reports derive all three pairwise summaries
from those independently assigned per-condition check grades.

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

Without `--candidate`, `results.json` remains schema version 1 with the existing
top-level fields, two behavior runs, task counts, reports, reproduction command,
and current-versus-baseline metrics. The `skill` condition ID and
`skill.runtime_digest_sha256` continue to identify Current for existing
consumers.

Candidate runs use schema version 2 and add:

- `candidate.path` and `candidate.runtime_digest_sha256`, separate from the
  Current digest under `skill.runtime_digest_sha256`;
- `candidate_trigger`, alongside the unchanged Current `trigger` path;
- `candidate_run` and `candidate` grades for each behavior result;
- `behavior.summary.comparisons` entries named `current_vs_baseline`,
  `candidate_vs_baseline`, and `candidate_vs_current`.

The existing `behavior.summary.absolute_lift`,
`lift_percentage_points`, and `paired_checks` fields remain the unambiguous
Current-versus-Baseline comparison in both schemas. Candidate mode reports use
the user-facing labels Baseline, Current, and Candidate. It measures evidence;
it does not decide whether to promote the candidate.

Running evaluations requires an authenticated Codex CLI. The evaluator links
the existing Codex authentication file into a temporary isolated home and
removes that home after each turn.

Candidate comparison is available through `--candidate`. Regression ingestion,
capability-review gates, context metrics, model profiles, and component
ablation remain separate work tracked in the [roadmap](../ROADMAP.md). The
[capability-optimisation contract](capability-optimisation.md) defines the
evidence standard for that planned tooling.

## Capability-review boundary

Future capability reviews will use baseline, current, and candidate conditions
to answer two distinct questions. Whole-skill efficacy asks whether the complete
skill improves on baseline. Component marginal value asks whether a coherent
part still improves the complete skill enough to justify its discovery,
activation, or conditional context cost.

Capability evidence must identify its skill universe. The default repository
universe includes peer skills in every condition and reflects normal
deployment. `--skill-universe isolated` removes those peers and helps separate
the target skill's value from sibling-skill coverage. Repository-mode coverage
by a peer is not evidence that the raw model provides the behavior. A complete
capability review inspects both universes or records the limitation.

The current task runner is Codex. Model selection through `--model` and
`--judge-model` therefore produces Codex model-profile evidence, not behavioral
evidence for every harness supported by the packaging system.
