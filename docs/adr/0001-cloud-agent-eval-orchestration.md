# ADR 0001. Cloud Agent eval orchestration

## Status

Accepted. Phase A removed the Codex live matrix. This change lands the
playbook and domain schemas. No runner code. No second Python matrix.

## Context

`skills-nexus` still proves skill changes through a Codex-shaped Python live
matrix. The live path centers on `scripts/eval_skills.py`,
`scripts/skill_eval/`, and the only registered production adapter in
`scripts/skill_eval/adapters/codex.py`. Capability review and ablation CLIs
compose that same matrix. Cursor CLI production adapters are closed as not
planned. ROADMAP already names Cursor Cloud Agents as the foundry operator and
demotes live Codex matrices.

Issue #74 asks for a swarm evidence contract before new prove-path code.
Mark will not use Codex going forward.

The static floor must survive. `scripts/validate_repo.py`,
`scripts/check-skills.sh`, and `scripts/check-quality.sh` remain the quality
gate. Observation triage under `scripts/skill_observation/` and
`scripts/skill_triage/` stays. Agent Plugin packaging under `plugins/` stays.
Repository-owned cases under `evals/` stay unless a file is Codex pilot scrap.

## Decision

Orchestration moves into Cloud Agent playbooks and prompts. It does not move
into a second Python matrix runner.

### Domain model

| Type | Meaning |
| --- | --- |
| `SkillVariant` | Digest-pinned skill snapshot. Roles are `current`, `baseline`, or `candidate`. Role ids stay parent-only. |
| `EvalCase` | One row from `evals/<skill>/evals.json` (trigger or behavior). Parent-only. Workers never receive this object. |
| `BlindedCandidateRun` | One comparable cell. Parent stamps pinned inputs. Worker delivers a project-shaped note. Judge sees a sanitized label only. |
| `JudgeRubric` | Three to six concrete criteria. Judge-only. Held back from workers. |
| `EvidenceSummary` | Human-authored durable record. Only export allowed under `evals/<skill>/reviews/`. |
| `HarnessTarget` | Closed value `cursor-cloud-agent`. No Codex member. |

Boundaries follow the pstack Eval playbook.

1. Frame the rubric for the judge only.
2. Sanitize each worker environment. No eval vocabulary in paths or prompts.
3. Author one organic prompt.
4. Spawn N blinded candidates on arena models.
5. Spawn one blinded judge on a different model family.
6. Verify chain-following from that workspace's transcripts, not self-report.
7. Human reads every output and synthesizes.

### Model roles (Mark's pstack map)

| Role | Model |
| --- | --- |
| Parent, feature, refactoring | `cursor-grok-4-6-xhigh-fast` |
| Bugfix, perf, hillclimb | `claude-opus-4-6-thinking-high` |
| Judgment, prose, hardest, judge | `claude-fable-4-6-thinking-high` |
| Arena runners | `cursor-grok-4-6-xhigh-fast`, `claude-opus-4-6-thinking-high`, `kimi-k2.5-max` |
| Swarm workers | `cursor-grok-4-6-xhigh-fast` |

### Issue #74 evidence contract (draft)

Pinned inputs per worker

- skill digest, plugin digest, logical skill name
- case id and kind, fixture digest, evals.json digest
- git sha, harness (`cursor-cloud-agent`)
- model and variant id (sealed from the judge)

Comparable outputs

- transcript ref local to that workspace
- declaration `PASS` / `ISSUES` / `BLOCKED`
- changed-file digests and workspace digest
- sanitized label for judge-facing joins

Parent aggregation

- `rank-all` for comparative prove (default)
- `first-pass` for reproduction slices (never greens a comparative PR alone)
- `best-of` diagnostic only (never greens a PR)

Named limits

- no automatic negative-activation metric from transcripts alone
- no CapOpt non-inferiority percentages from a few chats
- no cross-harness claim from Cloud Agent cells
- no auto-promote from eligibility or judge integers

Do not implement swarm runner code until this contract lands in schemas and
the playbook. Drafting the contract is in scope for the architecture track.
Expanding runner automation is not.

### What Python keeps

After Phase A, Python keeps a thin catalog module (proposed
`scripts/eval_cases.py` extracted from `scripts/skill_eval/core.py`) that

- loads and validates `evals.json`
- resolves skills for `validate_repo` and observation promote
- copies runtime skill trees and digests packages for packaging

A later pure evidence helper may parse and fold already-written run artifacts.
It must not spawn agents.

That helper (PR-C) enforces evidence rules in code, not only in playbook prose.

- Blinding is a file boundary. Parent emits a worker-facing task file and a
  sealed parent ledger. Eval vocabulary in a worker-facing field refuses emit.
- Admission is a type boundary. Untrusted worker returns stay private until
  `admit` checks pinned digests and derives transcript digests. An admitted
  `BlindedCandidateRun` with unverified pins is unrepresentable.
- Named limits are computed from platform caps, sample size, waivers, and
  judge presence. Limits that cap the verdict hold `INCONCLUSIVE`. Chats alone
  cannot go green.
- Each worker writes one identity-named file. Merge happens once at admit.
  No shared mutable run log across VMs.

### What Python loses

Live matrix orchestration, Codex adapters and runners, live capability review
and ablation CLIs, Codex eval profiles, and the `codex` deploy harness
requirement. Full path inventory lives in
`docs/eval-retirement-inventory.md`.

## Architecture sketch

```text
docs/eval-orchestration.md     playbook (modes, blinding, spawn, synthesize)
docs/eval-types/*.schema.json  SkillVariant, EvalCase, BlindedCandidateRun,
                               JudgeRubric, EvidenceSummary, HarnessTarget
evals/<skill>/evals.json       case catalog (kept)
scripts/eval_cases.py          load_eval_spec / resolve_skill / digests
scripts/validate_repo.py       static floor (kept, retargeted imports)
scripts/skill_observation/**   observation capture (kept)
scripts/skill_triage/**        promote into evals.json (kept)
plugins/**                     Agent Plugin packages (kept)
.foundry/runs/<id>/            gitignored parent ledger (not worker-mounted)
```

Playbook modes

- `prove-variant`. Current versus candidate. One organic prompt. Arena
  workers. One blinded judge. Human `EvidenceSummary`.
- `swarm-slice`. Assign catalog cases to isolated workers for reproduction or
  coverage. Weaker evidence. Cannot green a comparative PR alone.

## Consequences

Positive

- Eval shape matches how the foundry already operates.
- Codex surfaces can leave without waiting for a full prove rewrite.
- Blinding rules live in types and playbook structure, not in ad-hoc redaction.
- Static CI stays the merge floor.

Negative / accepted

- Human synthesis is a bottleneck. That is intentional.
- Transcript-only evidence is weaker than Codex matrices for negative
  activation and CapOpt non-inferiority. Named limits record that.
- Parent spawn API details may stay human-driven until product hooks exist.

## Alternatives rejected

1. Keep the Python matrix and swap a Cloud Agent adapter into the registry.
   Rejected. Preserves the wrong public surface and invites eval language back
   into candidate paths.
2. Docs-only playbook with no schemas and no artifact checks.
   Rejected. Issue #74 becomes unenforceable prose.
3. Large Python aggregator that walks run trees and auto-greens PRs.
   Rejected. Becomes a second orchestrator.

Arena sketches compared playbook-owned orchestration with artifact-owned run
records. The chosen shape keeps playbook ownership for spawn and blinding, and
adopts artifact schemas plus a pure fold helper from the artifact sketch.
Orchestration stays out of Python.

## Phase split

Phase A can land alone. Extract the thin catalog loader. Delete Codex live
surfaces. Keep `evals/` cases and static validation green. Later phases land
the playbook, schemas, evidence fold, and the first prove-variant rehearsal.
See `docs/eval-orchestration-plan.md`.
