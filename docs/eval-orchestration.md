# Cloud Agent eval orchestration

Parent-facing playbook for proving skill changes. Python does not spawn
agents. The catalog loader in `scripts/eval_cases.py` stays thin.

Types live in `docs/eval-types/`:

| Type | Who sees it |
| --- | --- |
| `SkillVariant` | Parent |
| `EvalCase` | Parent. Workers never receive this object. |
| `BlindedCandidateRun` | Parent after admit |
| `JudgeRubric` | Judge only |
| `EvidenceSummary` | Humans. Only durable export under `evals/<skill>/reviews/` |
| `HarnessTarget` | Closed value `cursor-cloud-agent` |

Issue [#74](https://github.com/mark-groves/skills-nexus/issues/74) is the
evidence contract. These schemas are that contract.

## Modes

`prove-variant` compares current versus candidate. One organic prompt. Arena
workers. One blinded judge. A human writes the `EvidenceSummary`. Default
aggregation is `rank-all`.

`swarm-slice` assigns catalog cases to isolated workers for reproduction or
coverage. Weaker evidence. It cannot green a comparative PR alone.
Aggregation is `first-pass`.

`best-of` is diagnostic only. It never greens a PR.

## Blinding

The observer effect is the failure mode. Candidates that know they are being
evaluated behave differently.

- No `eval`, `test`, `judge`, `experiment`, `rubric`, `score`, `compare`,
  `benchmark`, `candidate`, or `arena` in any directory, file, or prompt the
  worker sees.
- The worker prompt looks like an organic user request. State the goal, not
  the meta.
- No chain-eliciting cues. Do not ask the worker to list skills or
  principles. Grade chain-following from files it opened and the shape of
  the work.
- Sanitize directory and slug names. Use project-shaped names.
- Do not tell a worker that other workers exist.
- The judge may know it is judging. It sees outputs by `sanitized_label`
  only. It never sees a model name or `variant_id`.
- Role ids stay parent-only.

Blinding is a file boundary. The parent writes a worker-facing task file and
a sealed parent ledger. Eval vocabulary in a worker-facing field refuses
emit. That check lands in the PR-C helper.

## Prove-variant steps

1. Frame the rubric for the judge only. Three to six concrete criteria.
2. Pin `SkillVariant` digests for current and candidate. Pin the `EvalCase`
   row, fixture digest, `evals.json` digest, git sha, and harness
   `cursor-cloud-agent`.
3. Sanitize each worker environment. Install the pinned package. No eval
   vocabulary in paths or prompts.
4. Author one organic prompt.
5. Spawn N blinded candidates on arena models.
6. Spawn one blinded judge on a different model family.
7. Verify chain-following from that workspace's transcripts, not self-report.
8. Admit worker returns. Untrusted notes stay private until pins match and
   transcript digests are derived. An admitted `BlindedCandidateRun` with
   unverified pins is unrepresentable.
9. A human reads every output and writes the `EvidenceSummary`.

## Issue #74 fields

Pinned inputs per worker

- skill digest, plugin digest, logical skill name
- case id and kind, fixture digest, `evals.json` digest
- git sha, harness `cursor-cloud-agent`
- model and variant id, sealed from the judge

Comparable outputs

- transcript ref local to that workspace
- declaration `PASS` / `ISSUES` / `BLOCKED`
- changed-file digests and workspace digest
- sanitized label for judge-facing joins

Parent aggregation

- `rank-all` for comparative prove. Default. The only aggregation that may
  choose `promote`.
- `first-pass` for reproduction slices. Never greens a comparative PR.
- `best-of` diagnostic only. Never greens a PR.

## Named limits

These limits cap the verdict at `inconclusive` when they apply.

- No automatic negative-activation metric from transcripts alone.
- No CapOpt non-inferiority percentages from a few chats.
- No cross-harness claim from Cloud Agent cells.
- No auto-promote from eligibility or judge integers.
- `first-pass` and `best-of` cannot choose `promote`.
- Chats alone cannot go green.

Record every limit that held in `EvidenceSummary.limits_held`.

## Model roles

Use Mark's map. Do not invent slugs.

| Role | Model |
| --- | --- |
| Parent, feature, refactoring | `cursor-grok-4.6-xhigh-fast` |
| Bug-fix, perf, hillclimb | `claude-opus-5-thinking-high` |
| Judgment, prose, hardest, judge | `claude-fable-5-1-thinking-high` |
| Arena runners | those three plus `kimi-k3-max` |
| Swarm workers | `cursor-grok-4.6-xhigh-fast` |

If a named slug is unavailable in the current session, drop that arm and
record the gap. Do not substitute a different model.

## Artifacts

Parent ledger lives under `.foundry/runs/<id>/` and is gitignored. Workers
do not mount it. Each worker writes one identity-named file. Merge happens
once at admit. No shared mutable run log across VMs.

The only committed prove export is a human `EvidenceSummary` under
`evals/<skill>/reviews/`.

## What Python does

`scripts/eval_cases.py` loads catalogs. `scripts/eval_evidence.py` emits a
worker-facing task and a sealed ledger, admits one identity-named return
after deriving transcript digests, and folds admitted cells into an
`EvidenceSummary`. It does not spawn agents. Orchestration stays in this
playbook.
