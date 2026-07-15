# Continuous improvement

Skills Nexus uses an offline, evidence-gated learning loop. Agents may report
what happened during a skill run, but they do not rewrite installed skills or
promote their own suggestions directly.

```text
skill run
   -> structured observation
   -> validation, redaction, and triage
   -> reproducible regression case
   -> candidate change
   -> current-versus-candidate proving grounds
   -> reviewed pull request
   -> publish and observe again
```

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
accepted for triage. A later triage stage must validate and redact again; schema
validation alone does not make task content safe.

## Triage

Triage validates the observation before changing a skill:

- confirm the reported skill revision and environment;
- remove secrets, personal data, unrelated task content, and unsupported claims;
- deduplicate the report against existing observations and evals;
- classify the likely change surface: trigger description, instructions, script,
  reference, packaging, harness adapter, or environment;
- decide whether the behavior is reproducible and important enough to retain.

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
