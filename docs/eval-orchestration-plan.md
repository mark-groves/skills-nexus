# Cloud Agent eval orchestration plan

Planning deliverable for the Codex retirement and Cloud Agent prove path.
Execution starts only on an explicit operator go. The execution playbook is
`playbooks/autopilot-stack.md` (operator lands the stack; this agent does not merge).

## Recommended stack

| PR | Intent | Depends on |
| --- | --- | --- |
| This planning PR | ADR, inventory, this plan | None |
| PR-A | Retire Codex live matrix. Keep thin `evals.json` loader and static floor. | Planning PR merge |
| PR-B | Land orchestration playbook, domain schemas, and #74 contract fields. | PR-A |
| PR-C | Land pure evidence check and summarize helper (no agent spawn). | PR-B |
| PR-D | Rehearse one `prove-variant` on a single skill. Record receipts. | PR-C |

Why Phase A splits first

- `validate_repo` and observation promote need catalog parse, not Codex.
- ROADMAP already demoted live Codex matrices.
- Deleting the live runner shrinks the redesign surface before new prove work.
- Splitting is wrong only if someone still needs Codex matrices on main during
  the architecture track. Mark does not.

## Domain reminder

`SkillVariant`, `EvalCase`, `BlindedCandidateRun`, `JudgeRubric`,
`EvidenceSummary`, `HarnessTarget` (`cursor-cloud-agent` only). Full decision
record is `docs/adr/0001-cloud-agent-eval-orchestration.md`. Path-level delete
and keep lists are `docs/eval-retirement-inventory.md`.

## Checkable owner plan

The box-level owner checklist that `check-plan.mjs` validates lives at
`/cursor/stores/self/docs/cloud-agent-eval-plan.md` in the planning agent
store. It names the same PR-A through PR-D sequence with unit, live, and perf
predicates.

## Operator go line

After this planning PR is reviewed, reply with `go` (or name a subset such as
`go PR-A only`). Owners then run under autopilot-stack and stop at merge-ready.
