# Continuous improvement

Skills Nexus uses an offline, evidence-gated learning loop. Agents may report
what happened during a skill run, but they do not rewrite installed skills or
promote their own suggestions directly.

```text
Corrective improvement
skill run
   -> structured observation
   -> validation, redaction, and triage
   -> reproduced failure and regression case
   -> corrective candidate
   -> current-versus-candidate proof
   -> reviewed pull request

Capability optimisation
model or runtime progression
   -> documented redundancy hypothesis
   -> reduced candidate
   -> protected, full-suite, and required-profile gates
   -> current-versus-candidate non-inferiority proof
   -> reviewed pull request
```

Both paths publish and observe again after review. A context reduction does not
require a fabricated failure; it requires stronger comparative evidence that
the proposed reduction preserves supported behavior. See the
[capability-optimisation contract](capability-optimisation.md) for the context
budgets, model profiles, skill universes, evidence gates, verdicts, and
retirement criteria. That contract describes planned tooling and does not
change current evaluator behavior.

## Observation boundary

An observation records three different kinds of information:

1. **Facts** — outcome, errors, commands, artifacts, obstacles, instruction
   sections consulted, and workarounds used.
2. **Diagnosis** — the reporting agent's explanation of why the run was easy or
   difficult, including a confidence level.
3. **Proposal** — an optional suggested change. A proposal is never treated as
   authoritative merely because an agent produced it.

Each record must identify the skill name and runtime digest. When available it
also records the repository revision, harness, model, invocation mode, and a
bounded task summary. This makes feedback attributable to the instructions that
actually ran rather than whichever version is currently checked out.

Raw observations belong in `.skill-feedback/inbox/`, which is ignored by Git.
They may contain user data, model output, untrusted task content, or prompt
injection. Do not commit raw transcripts. Accepted evidence should be reduced to
the smallest redacted regression fixture and assertions needed to reproduce the
behavior.

## Record an observation

The initial capture adapter accepts a strict JSON draft no larger than 64 KiB.
It rejects arbitrary fields and full transcripts, adds repository and skill
provenance, marks the record untrusted, and writes a private file with mode
`0600`.

```json
{
  "schema_version": 1,
  "source": {"kind": "agent", "external_run_id": "run-123"},
  "runtime": {
    "harness": "codex",
    "harness_version": null,
    "model": "example-model",
    "invocation": "automatic",
    "activation": "activated"
  },
  "task": {
    "category": "git",
    "summary": "Prepared a commit from a mixed working tree."
  },
  "outcome": "partial",
  "signals": [
    {
      "kind": "instruction_confusion",
      "observation": "The agent reconsidered the same grouping twice.",
      "instruction_ref": "SKILL.md: Split decision",
      "evidence_excerpt": "Two consecutive planning steps revisited the grouping.",
      "diagnosis": "The split-commit stop condition was unclear.",
      "diagnosis_confidence": "medium"
    }
  ],
  "suggested_change": "Add one positive and one negative grouping example."
}
```

Record it against the exact canonical skill that ran:

```bash
python3 scripts/record_observation.py \
  --skill commit \
  --input /path/to/observation.json
```

The versioned draft contract is also published as
[`schemas/skill-observation-draft-v1.schema.json`](../schemas/skill-observation-draft-v1.schema.json).
The recorder adds a generated observation ID and timestamp, `trust: untrusted`,
the canonical runtime SHA-256 digest, and the current Git commit/dirty state.
Stored inbox records match
[`schemas/skill-observation-stored-v1.schema.json`](../schemas/skill-observation-stored-v1.schema.json).
Harness adapters should populate their real harness, version, model, invocation,
activation, and external run identifier rather than guessing.

Allowed signal kinds are `worked`, `obstacle`, `instruction_confusion`,
`instruction_gap`, `instruction_conflict`, `workaround`,
`unexpected_behavior`, and `other`. Evidence excerpts are bounded supporting
facts, not a place to paste prompts, conversations, source files, credentials,
or personal data.

Capture is opt-in until a harness adapter provides an explicit consent and
retention policy. Redact secrets and identifying data before recording. Keep the
private inbox local, restrict its retention, and delete records that are not
accepted for triage. Schema validation alone does not make task content safe.
Triage validates the stored record and redacts it again before any classification
or promotion.

## Triage

Triage does not edit the inbox file or `SKILL.md`. It writes a redacted copy and
a disposition under `.skill-feedback/triage/`, which Git ignores. Classify first.
Matching fingerprints are the cluster. Query them with `cluster_for` over
disposition records that share a fingerprint. There is no separate cluster CLI.
The hash covers the redacted skill id and the signal kind, instruction pointer,
observation text, and diagnosis. It ignores outcome, task metadata, suggested
changes, runtime fields, evidence excerpts, and diagnosis confidence.

Classifications are `instruction`, `trigger`, `script`, `reference`,
`deployment`, and `environment`. Disposition records match
[`schemas/skill-observation-disposition-v1.schema.json`](../schemas/skill-observation-disposition-v1.schema.json).

```bash
python3 scripts/classify_observation.py \
  --input .skill-feedback/inbox/commit/<observation-id>.json \
  --class instruction
```

To inspect a redacted copy without classifying:

```bash
python3 scripts/redact_observation.py \
  --input .skill-feedback/inbox/commit/<observation-id>.json
```

If the report is not reproducible, or is not a skill defect, close it without
editing `evals.json`:

```bash
python3 scripts/reject_observation.py \
  --input .skill-feedback/inbox/commit/<observation-id>.json \
  --disposition insufficient \
  --reason "Excerpt does not reproduce against the current skill."
```

`--disposition` may be `reject` or `insufficient`. The default is `reject`.

If the behavior is reproducible, promote a trigger case, a behavior case, or
both into `evals/<skill>/evals.json`. When `capability-case-groups.json` exists,
new case ids go to the `development` group unless you pass `--group`. Promotion
does not edit the skill. `deployment` and `environment` classifications cannot
be promoted.

```bash
python3 scripts/promote_observation.py \
  --input .skill-feedback/inbox/commit/<observation-id>.json \
  --reason "Stopping condition is ambiguous and reproducible." \
  --trigger-query "split these changes into two commits" \
  --should-trigger true \
  --behavior-prompt "/commit split the staged Python and docs changes" \
  --expected-behavior "Stops after one split decision and does not regroup." \
  --check "States the split stop condition once"
```

`load_eval_spec` must accept the updated suite before the write replaces
`evals.json`. Fixture paths must also resolve under the skill's eval directory,
the same rule `validate_repo` uses. Identical trigger or behavior content reuses
the existing case id instead of appending a duplicate.

Some observations should result only in a new eval, a deployment fix, or no
change. More instructions are not the default answer to every failed run.

## Proving grounds

An accepted behavioral problem becomes a regression case before a candidate is
written. The proving sequence is:

1. Run the regression against the current skill and confirm the failure.
2. Generate or author a candidate change without exposing held-back cases.
3. Compare the candidate with the current skill in fresh, equivalent contexts.
4. Run the complete trigger and behavior suite to find regressions.
5. Repeat variable cases and inspect execution traces, cost, and tool use.
6. Produce a report containing the observation identifier, digests, results,
   limitations, and reproduction commands.

The existing evaluator already provides fresh contexts, paired baseline runs,
label-blinded grading, fixtures, repeats, and preserved evidence. Candidate
comparison extends that model; it does not replace skill-versus-baseline
measurement.

## Promotion

Automation may prepare a branch and pull request after all configured gates pass.
It must not merge directly. Reviewers should be able to see:

- the normalized observation and its provenance;
- the regression that failed against the current skill;
- the candidate diff;
- candidate-versus-current and full-suite results;
- efficacy, regression, variance, cost, and integrity warnings;
- any behavior that could not be verified.

The committed regression case becomes the durable memory of the incident. Raw
feedback can then be expired according to the repository's retention policy.

For a context reduction, the durable memory is instead a bounded capability
summary. Raw prompts, transcripts, event traces, workspaces, and generated task
artifacts remain local and ignored. A summary records pinned digests and model
profiles, both skill universes, repeated and held-back coverage, separate gate
outcomes, context savings, uncertainty, reproduction commands, and a reviewed
verdict.
