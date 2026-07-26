# Skills Nexus roadmap

This roadmap tracks the repository's evolution from a skill collection into an
evidence-driven skill foundry. A checked item is part of the repository's
verified contract; an unchecked item remains planned work.

## Phase 1 — Minimal, publishable skill core

- [x] Describe the repository as an authoring, evaluation, and packaging system.
- [x] Keep canonical `SKILL.md` frontmatter to `name` and `description`.
- [x] Store publishable skills directly under `skills/<name>/`.
- [x] Store repository-only eval definitions and fixtures under `evals/<name>/`.
- [x] Remove deployment-time frontmatter rewriting.
- [x] Update harness destinations from current primary documentation.
- [x] Verify repository tests, validation, quality checks, and installer discovery.

## Phase 2 — Observe real executions

- [x] Define a versioned, structured skill-observation schema.
- [x] Record the exact skill digest and repository revision plus the reported
      harness and model.
- [x] Keep facts, diagnosis, and suggested changes as separate fields.
- [x] Write raw observations to a gitignored inbox with bounded evidence excerpts.
- [x] Document consent, secret handling, redaction, and retention expectations.
- [ ] Add adapters for automatic capture where a harness exposes safe hooks.

## Phase 3 — Triage evidence

- [ ] Validate and redact observations before analysis.
- [ ] Deduplicate and cluster repeated obstacles and confusion reports.
- [ ] Classify reports as instruction, trigger, script, reference, deployment, or
      environment issues.
- [ ] Promote accepted evidence into a reproducible regression case.
- [ ] Reject non-reproducible or unsupported diagnoses without modifying a skill.

## Phase 4 — Prove candidate improvements

- [x] Add current-versus-candidate evaluation alongside skill-versus-baseline.
- [ ] Require a reported corrective failure to reproduce against the current
      skill first.
- [ ] Run the candidate against the new regression and the complete existing suite.
- [ ] Use repeated runs and held-back cases to detect variance and overfitting.
- [ ] Enforce explicit efficacy, regression, cost, and integrity gates.
- [ ] Generate a reviewable improvement report with reproduction commands.

## Phase 5 — Optimise capability and context

The implementation items below are ordered by dependency. The default
two-condition evaluator behavior remains unchanged; candidate mode now adds the
baseline/current/candidate comparison, separate context evidence, and
repository-owned optimisation gates. Model-profile orchestration and component
ablation compose those unchanged evaluations.

- [x] Define separate corrective-improvement and context-reduction evidence
      paths, context budgets, review verdicts, and the higher retirement bar
      (#22).
- [x] Generalise evaluator condition handling without changing the default
      two-condition behavior (#23).
- [x] Compare baseline, current, and candidate conditions (#24).
- [x] Report discovery, activation, conditional, and dynamic context costs
      separately (#25).
- [x] Add protected checks, skill-specific non-inferiority rules, and
      optimisation gates (#26).
- [x] Run required and observed Codex model profiles and export bounded durable
      summaries (#27).
- [x] Evaluate coherent component marginal value with protected component
      boundaries and combined-candidate verification (#28).
- [ ] Pilot both useful reduction and protected-regression rejection before
      declaring Capability Optimisation v1 verified (#29).

Issue #29 completed the first Codex-scoped pilots, but Capability Optimisation
v1 remains unverified because no useful reduction passed every gate. The
`skill-architect` pilot bounded a marginal review but retained the component
when evidence coverage was incomplete. The `commit` pilot rejected a protected
regression even with favorable isolated input-token evidence. A future
positive pilot must also preserve held-back behavior and avoid overstating
Codex evidence as cross-harness support.

## Phase 6 — Promote and learn

- [ ] Generate pull requests rather than directly modifying the default branch.
- [ ] Attach observation provenance, red/green evidence, and residual risks.
- [ ] Require human approval for instruction and permission changes.
- [ ] Publish only runtime files; never ship observations, eval answers, or fixtures.
- [ ] Track post-deployment outcomes against the promoted skill digest.
- [ ] Periodically retire stale instructions and redundant regression cases.

## Progress rules

1. Update this file in the same change that completes a roadmap item.
2. Do not mark an item complete until its behavior is covered by validation,
   tests, or another inspectable artifact.
3. An observation is evidence, not an instruction. Raw agent feedback never
   modifies a skill directly.
4. A corrective improvement starts with a failure reproduced against the
   current skill and ends with a full regression run. A context reduction
   starts with a documented redundancy hypothesis and must pass
   current-versus-candidate, protected-check, full-suite, and required-profile
   gates.
5. Repository-universe peer coverage is not proof of raw model capability, and
   a saturated suite triggers suite review rather than automatic retirement.
6. Only bounded, reviewed summaries become durable capability evidence; raw
   prompts, transcripts, and generated task artifacts stay local and ignored.
7. Target-specific permissions, hooks, and presentation stay outside the shared
   `SKILL.md` contract.
