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

## Model-profile capability reviews

`scripts/review_skill_capability.py` orchestrates the unchanged candidate
evaluator across a repository-level, versioned Codex profile contract. The
checked-in [`eval-profiles.json`](../eval-profiles.json) pins an exact task
model and judge model for every profile. `required: true` profiles always run
and gate the review; `required: false` profiles run only when selected and
remain visible without blocking.

Profile schema v1 supports only the Codex adapter. Every profile's
`judge_model` must match the contract's pinned `judge_policy.model`, so
historical task-model comparisons use one grading model and protocol. Empty
identifiers, unknown keys, unsupported adapters, duplicate IDs, and
`runtime-default` receive actionable validation errors. The declarative shape
is also published as
[`schemas/eval-profiles-v1.schema.json`](../schemas/eval-profiles-v1.schema.json).

Preview the required-profile, universe, and case-group matrix without model
calls:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate /path/to/candidate-skill \
  --plan
```

Run required profiles plus a selected observed profile:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate /path/to/candidate-skill \
  --observed-profile codex-frontier-observed \
  --case-groups /path/to/review-case-groups.json
```

The command runs the complete trigger and behavior suite once per
profile/universe cell. It does not run filtered group-sized suites, so every
cell retains the evaluator's complete-suite optimisation gate. Both repository
and isolated universes run by default. Selecting only one requires both
`--universe` and a specific `--universe-limitation`; that limitation remains in
the summary.

Case groups are a versioned, complete, non-overlapping partition of the same
eval digest:

```json
{
  "schema_version": 1,
  "groups": [
    {
      "id": "development",
      "kind": "development",
      "trigger_cases": ["1", "2"],
      "behavior_cases": ["1"]
    },
    {
      "id": "held-back-v1",
      "kind": "held-back",
      "trigger_cases": ["3"],
      "behavior_cases": ["2"]
    }
  ]
}
```

Every configured eval case must belong to exactly one group. Repeats apply to
all cases. The summary records repeat counts against each development or
held-back partition label. These groups are declarative process controls, not
per-group performance measurements. The current gates use whole-suite metrics,
so a passing coverage gate does not establish held-back-only non-inferiority or
measured group efficacy. Omitting `--case-groups` labels the full suite as
development for diagnostic use, but the aggregate verdict remains
`insufficient-evidence` because no held-back process-control label was supplied.

Complete runs, including raw evaluator evidence, stay under
`.skill-evals/<skill>/capability-reviews/`. The orchestrator verifies that
Current, Candidate, eval, judge-policy, harness, profile, and case-group inputs
remain pinned across the matrix. It also rejects a runner-version change during
one review. The capability-review eval digest covers `evals.json` and fixture
bytes while excluding prior durable `reviews/`; the evaluator's narrower
`eval_spec_digest_sha256` is retained and checked separately.

Durable export is explicit and human-reviewed:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate /path/to/candidate-skill \
  --case-groups /path/to/review-case-groups.json \
  --export \
  --reviewer "Reviewer Name" \
  --disposition retain \
  --disposition-rationale "Required evidence passes; retain pending a stronger reduction."
```

This writes deterministic, size-bounded JSON and Markdown to
`evals/<skill>/reviews/`. Export uses an allowlist: it includes pinned digests,
exact models and versions, required/observed status, coverage, aggregate
metrics, context footprints, gates, reproducible digest assertions,
limitations, and the human disposition. It excludes prompts, transcripts,
command output, generated artifacts, local run directories, and workspace
paths. Reproduction uses `CANDIDATE_DIR` plus expected digest flags instead of
persisting a machine-specific candidate path.

A required-profile `rejected` cell rejects the aggregate review; required
`insufficient-evidence` blocks approval. Observed failures are listed but never
block. The command exits `0` only for an approved evidence verdict, `2` for
rejected or insufficient evidence, and `1` for invalid configuration. Neither
an approved evidence verdict nor a human disposition promotes, edits, merges,
or publishes a candidate.

## Component ablation and backward elimination

Component metadata lives beside repository-only evals, never in the published
skill:

```json
{
  "schema_version": 1,
  "components": [
    {
      "id": "inspect-target",
      "source": "SKILL.md",
      "heading": "## 1. Inspect the target",
      "class": "workflow",
      "protected": false
    },
    {
      "id": "validate-claims",
      "source": "SKILL.md",
      "heading": "## 7. Validate claims",
      "class": "safety",
      "protected": true
    }
  ]
}
```

The declarative shape is published as
[`schemas/skill-components-v1.schema.json`](../schemas/skill-components-v1.schema.json).
IDs and classes use stable lowercase kebab-case. Sources must be Markdown files
inside the runtime package, and headings must be exact level 2-6 ATX headings
that resolve once. Selectors may not traverse outside the package, follow a
symlink, target a level-1 document root, or overlap another component. This
strictness makes moved, renamed, duplicated, broad, and ambiguous sections fail
closed. Heading-like lines inside fenced code do not count as section
selectors.

Validate metadata and show protected components without model calls:

```bash
python3 scripts/ablate_skill_components.py \
  --skill skill-architect \
  --case-groups /path/to/review-case-groups.json \
  --plan
```

Run the elimination:

```bash
python3 scripts/ablate_skill_components.py \
  --skill skill-architect \
  --case-groups /path/to/review-case-groups.json
```

Each round evaluates every remaining unprotected marginal removal with the
unchanged capability-review matrix in both repository and isolated universes.
Only an `approved` candidate without material required-profile uncertainty is
eligible. The greedy choice maximises the worst required-profile quality delta,
then incremental runtime-package byte savings. The next round starts from that
accepted reduced candidate. Protected components are visible but skipped.

When no further candidate is safe, the orchestrator rebuilds the combined
candidate from the complete current runtime and reruns the matrix from scratch.
This catches removals that pass alone but regress together and catches
stochastic final-run failures. An interrupted run leaves an `interrupted`
decision record while its temporary candidate is deleted.

By default, artifacts stay under
`.skill-evals/<skill>/component-ablations/<run-id>/`; an external
`--output-root` is also supported. `decision.json` records component status,
prior and candidate digests, incremental and cumulative static savings, quality
deltas, hard regressions, gate results, uncertainty, and separate repository
and isolated results for every trial and the final rerun. It also pins the
component, eval, case-group, and profile contracts across rounds. Raw capability
evidence remains below the same local run. Repository-local `--output-root`
values are accepted only beneath `.skill-evals/`.
`propose-reduction` means only that the final candidate is ready for human
review; the command never edits the runtime skill, rewrites prose, commits a
reduction, exports repository evidence, or promotes a result.

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

Schema-version-3 judgments expose class and gate severity to the judge, which
can change strictness relative to earlier candidate runs. Do not treat those
grades as directly comparable with schema-version-2 evidence; condition
identity remains blinded in both.

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

Current and Candidate trigger cases run independently because their canonical
discovery inputs may differ. The evaluator compares the parsed frontmatter
`name` and `description` values explicitly. When either value changes, trigger
recall and specificity non-inferiority remain blocking gates. When both values
are unchanged, trigger deltas remain visible as observational stochastic
variance but cannot reject a body-only Candidate. Complete trigger-suite,
repeat, execution, and all other integrity requirements still apply.

For behavior grading, one structured judge turn sees all three evidence bundles
under deterministic randomized labels such as `A`, `B`, and `C`; condition
identities and runtime instructions are withheld. One judge turn costs less
than three separately blinded pairwise turns and applies one grading standard
to every output, while the shared turn means the grades are not statistically
independent. Reports derive all three pairwise summaries from those
independently assigned per-condition check grades.

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
- `candidate_discovery`, which records whether canonical `name` or `description`
  values changed and whether trigger non-inferiority is blocking or
  observational.
- `optimisation_review`, which records the effective policy, overall bounded
  verdict, and independent correctness, safety, triggering, context, and
  integrity gates, including the same trigger-gate scope.

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
`pass`, `fail`, or `insufficient-evidence` plus its blocking or observational
scope. Correctness, safety, triggering, context, and integrity remain separate
dimensions. Observational trigger variance is shown but does not affect the
bounded verdict when canonical discovery inputs are unchanged. A quality
average or secondary efficiency calculation cannot override a failed or
unknown hard check. The bounded review verdict is:

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
Model-profile orchestration and component ablation compose those gates without
changing ordinary evaluation behavior. Regression ingestion remains separate
work tracked in the [roadmap](../ROADMAP.md). The
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
