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
symlinks, and creates clean immutable Current and Candidate runtime snapshots.
Their snapshot digests are recorded before agent turns begin, so edits to either
source during a run cannot change the packages being evaluated.

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

## Checks and optimisation policy

Behavior checks remain backwards-compatible. A plain string is a normal
quality check:

```json
"Reports the created commit"
```

Protected or otherwise classified checks use an object:

```json
{
  "id": "do-not-commit-on-detached-head",
  "text": "Does NOT create a commit while HEAD is detached",
  "class": "safety",
  "gate": "hard"
}
```

Structured `id` values are stable lowercase kebab-case identifiers and must be
unique across the skill's eval suite. `class` is one of `quality`,
`correctness`, `safety`, or `local-contract`; `gate` is `normal` or `hard`.
Legacy strings are sent to the judge with generated case-and-position IDs,
`class: quality`, and `gate: normal`, while their existing report shape stays
unchanged. The judge receives this metadata but only sees randomized condition
labels, never Current, Baseline, or Candidate identities.

Candidate optimisation reviews use the optional repository-owned
`review_policy` block:

```json
{
  "review_policy": {
    "minimum_repeats": {
      "trigger": 2,
      "behavior": 2
    },
    "quality": {
      "non_inferiority_margin": 0.05,
      "minimum_lift_over_baseline": 0.05,
      "minimum_evidence_coverage": 1.0
    },
    "triggering": {
      "recall_non_inferiority_margin": 0.05,
      "specificity_non_inferiority_margin": 0.05
    },
    "context": {
      "minimum_reductions": {
        "description_characters": 20,
        "skill_md_body_characters": 100,
        "runtime_package_bytes": 1024,
        "dynamic_input_tokens": 100
      }
    },
    "integrity": {
      "allowed_fixture_fidelity": [
        "none",
        "files",
        "executable",
        "description-only"
      ],
      "require_fixture_parity": true,
      "require_blind_grading": true
    }
  }
}
```

The shown values are the conservative defaults for omitted policy fields.
Context reduction passes when at least one configured positive threshold is
met. Fixture fidelity, fixture parity, judge blinding, minimum repeats, complete
trigger-and-behavior coverage, and evidence coverage remain explicit integrity
gates. The default fidelity list accepts intact file, executable, empty, and
sanitized description-only fixtures; degraded, missing, and setup-failed
fixtures do not pass.

A wholly missing `review_policy` still evaluates every gate using those defaults
so results remain inspectable, but the policy gate is
`insufficient-evidence` and the optimisation can never be approved silently.
Unknown evidence on a hard protected check is also
`insufficient-evidence`, never a pass.

Approval also requires the exact full configured trigger and behavior case
sets. `--trigger-case`, `--behavior-case`, `--max-trigger-cases`, and
`--max-behavior-cases` remain useful for diagnostic candidate runs, but any
filtered or capped suite receives an `insufficient-evidence` complete-suite
gate and cannot exit as approved.

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
workspace changes, Git state, timing, detailed token use, tool calls, baseline
lift, and confidence limitations. Missing or failed fixtures are reported as
unknown instead of being treated as successful.

Every condition also has a portable `context_footprint` record. Description and
`SKILL.md` body sizes are reported as both Unicode characters and UTF-8 bytes.
The body is the exact text after the closing frontmatter delimiter, including
leading and trailing whitespace. Runtime-package file counts and raw bytes use
the same exclusions as runtime copying and digest calculation: repository-only
`evals/`, `working/`, Git metadata, and Python caches do not count. Empty
directories do not count as files, while empty files do. The recorded package
digest identifies the deterministic file tree used for those measurements;
Baseline has a zero footprint and no package digest.

Portable characters and bytes are the canonical static measurements. The
evaluator deliberately does not estimate tokens with a provider-specific
tokenizer. Dynamic `input_tokens`, `output_tokens`, and `total_tokens` come only
from actual task-runner usage, alongside median duration, tool calls, and
completed/failed run counts. If any completed run omits usage or supplies an
invalid usage value, the affected aggregate is `null` in JSON and shown as `—`
in Markdown and HTML, never as zero.

Without `--candidate`, `results.json` remains schema version 1 and additively
includes the top-level `context_footprint` field. Existing top-level fields, two
behavior runs, task counts, reports, reproduction command, and
current-versus-baseline metrics remain intact. The `skill` condition ID and
`skill.runtime_digest_sha256` continue to identify Current for existing
consumers.

Candidate runs use schema version 3 and add:

- `candidate.path` and `candidate.runtime_digest_sha256`, separate from the
  Current digest under `skill.runtime_digest_sha256`;
- `candidate.name`, `config.candidate` (the candidate path exactly as
  supplied), and `integrity.blind_condition_grading`;
- `candidate_trigger`, alongside the unchanged Current `trigger` path;
- `candidate_run` and `candidate` grades for each behavior result;
- `behavior.summary.comparisons` entries named `current_vs_baseline`,
  `candidate_vs_baseline`, and `candidate_vs_current`.
- `candidate_comparison`, which combines Candidate-minus-Current quality,
  Candidate lift over Baseline, static footprint reductions, dynamic input-token
  reduction, and Candidate wins/regressions/ties/unknowns.
- `optimisation_review`, which records the effective policy, overall bounded
  verdict, and independent correctness, safety, triggering, context, and
  integrity gates.

The existing `behavior.summary.absolute_lift`,
`lift_percentage_points`, and `paired_checks` fields remain the unambiguous
Current-versus-Baseline comparison in both schemas. Candidate mode reports use
the user-facing labels Baseline, Current, and Candidate. It measures evidence;
an `approved` review verdict does not edit, promote, or publish the candidate.

Candidate comparison signs are intentional: quality is Candidate minus the
named comparison, so positive means Candidate quality is higher. Context
reduction is Current minus Candidate, so positive means Candidate is smaller.
Dynamic input-token reduction is unknown when either side lacks runner usage or
when Current and Candidate do not have equal, fully completed behavior runs.
Configured review policy decides which of these measurements gate an
optimisation.

Every gate is reported in `results.json`, `report.md`, and `report.html` with
`pass`, `fail`, or `insufficient-evidence`. Correctness, safety, triggering,
context, and integrity remain separate dimensions. A quality average or
secondary efficiency calculation cannot override a failed or unknown hard
check. The bounded review verdict is:

- `approved` only when every applicable hard gate passes;
- `rejected` when measured evidence fails a gate;
- `insufficient-evidence` when policy, suite coverage, repeats, or required
  evidence is unavailable.

CLI exit status is unchanged for ordinary two-condition evaluation. Candidate
mode exits `2` for `rejected` or `insufficient-evidence`, and `0` only for an
approved review. Invalid configuration or invocation exits `1`; `--plan` exits
`0` after validation without claiming approval. `--fail-under` continues to
exit `2` when its threshold fails.

Running evaluations requires an authenticated Codex CLI. The evaluator links
the existing Codex authentication file into a temporary isolated home and
removes that home after each turn.

Candidate comparison and single-profile optimisation gates are available
through `--candidate`; context-footprint reporting is available in both modes.
Regression ingestion, model-profile orchestration, and component ablation
remain separate work tracked in the [roadmap](../ROADMAP.md). The
[capability-optimisation contract](capability-optimisation.md) defines the
broader evidence standard.

## Capability-review boundary

Capability reviews use baseline, current, and candidate conditions
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
