# Capability optimisation

Capability optimisation asks whether every part of a skill still earns its
runtime cost. It complements corrective improvement. Missing a known failure
is not proof that instructions are redundant.

The Codex live review and ablation CLIs are gone. Gate vocabulary stays so a
later Cloud Agent prove path can reuse it. Companion data under `evals/`
stays. See [ADR 0001](adr/0001-cloud-agent-eval-orchestration.md).

## Vocabulary that still matters

Routine language is deliberately non-approving:

- `reject` means selected substantive evidence failed.
- `incomplete` means coverage, integrity, or execution could not support a
  stronger claim.
- `eligible-for-escalation` means a bounded screen may be considered for a
  human-opted full review.

Eligibility never approves, exports, applies, promotes, or publishes a
candidate.

Whole-skill efficacy is the value of the complete current skill relative to
no skill. Component marginal value is the change from one coherent section
when a candidate is compared with the complete current skill. Those
comparisons are not interchangeable.

Repository-owned `evals/<skill>/components.json` still names coherent
section boundaries. `capability-case-groups.json` still partitions
development and held-back cases. `routine-screen.json` still names a
high-signal development slice. `validate_repo` loads those files. Nothing
executes them as a live matrix.

## Named limits

Transcript-only Cloud Agent cells are weaker than the retired Codex matrices
for automatic negative activation and CapOpt non-inferiority percentages. A
few chats cannot declare Capability Optimisation v1 verified. Cross-harness
claims from Cloud Agent cells are out of scope. Auto-promote from eligibility
or judge integers is out of scope.

Issue #29 Codex pilots remain historical scrap. They do not travel as
cross-harness support.

## What replaced the live path

A parent frames a rubric, sanitizes worker environments, and synthesizes a
human `EvidenceSummary`. Python may later fold already-written artifacts. It
must not spawn agents. The playbook and schemas for that path land after
this retirement.
