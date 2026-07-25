# Capability optimisation

Capability optimisation asks whether every part of a skill still earns its
runtime cost as models and harnesses change. It complements corrective
improvement; it does not lower the evidence standard or turn the absence of a
known failure into proof that instructions are redundant.

This guide defines the repository contract for capability-review tooling. The
current evaluator compares baseline, current, and candidate packages, reports
context metrics, and enforces repository-owned single-profile optimisation
gates. It does not yet orchestrate required and observed model profiles or
perform component ablation. Those implementation steps are tracked in the
[roadmap](../ROADMAP.md).

## Two evidence paths

| Change path | Starting evidence | Candidate goal | Required proof |
| --- | --- | --- | --- |
| Corrective improvement | A reported problem reproduced against the current skill | Correct the failure | The regression passes, the candidate improves on current, and the complete suite remains sound |
| Context reduction | A documented redundancy hypothesis | Remove, compress, relocate, or mechanise context without losing value | The candidate is non-inferior to current across required profiles, protected checks and the complete suite pass, and retained skill value over baseline remains justified |

A context reduction must not invent a failing case. Its hypothesis should name
the component, why a model or another resource may now supply the same value,
which context budget should fall, and what evidence could disprove the claim.
Both paths end in a reviewed pull request; neither authorises automatic
promotion.

## Context budgets

Capability reviews report three budgets separately because they are paid at
different times and have different effects:

- **Discovery context** is the skill's frontmatter `description`, made available
  so an agent can decide whether to activate the skill. Reducing it can save
  always-present selection context, but can also damage trigger recall or
  specificity.
- **Activation context** is the `SKILL.md` instruction body loaded when the
  skill activates. It is the main budget for procedures, decision rules, and
  safety stops.
- **Conditional context** is runtime material such as references, scripts, and
  assets that is loaded or used only when the workflow calls for it. Package
  bytes and dynamically loaded prompt context are distinct measurements.
  Moving content from activation context to a reference is a relocation, not a
  deletion, and only saves runtime context when agents reliably avoid loading
  that reference unnecessarily.

Static characters and bytes provide portable footprint evidence. Actual input
tokens, output tokens, tool calls, and duration provide runner-specific dynamic
evidence. A smaller budget is not evidence of equal behavior, and an aggregate
efficiency score cannot override a correctness, safety, triggering, or
integrity failure.

## Model profiles and evidence scope

A **model profile** identifies the task model, judge model, runner, harness, and
their relevant versions. The comparison record adds the evaluation digest and
review policy. Reviews distinguish:

- **Required profiles**, which define the supported model floor and gate a
  change. Every required profile must pass; optimising only for the most capable
  available model could silently raise that floor.
- **Observed profiles**, which record useful evidence about other models or
  configurations but do not gate promotion. Their failures and uncertainty
  remain visible.

Durable comparisons pin exact model and judge identifiers. A mutable runtime
default is not sufficient evidence, and results produced with different suites
or judge policies are not treated as directly comparable.

Skills Nexus packages skills for several harnesses, but the initial executable
capability evidence is **Codex model-profile evidence**. The repository does not
yet have equivalent runner adapters for other harnesses. Packaging
compatibility, or a successful Codex run using a model also exposed elsewhere,
is not cross-harness behavioral evidence.

## Skill universes

Each universe answers a different question:

- The **repository universe** makes peer Skills Nexus skills available to all
  conditions. It measures the target skill in its normal repository deployment
  and can expose overlap worth merging.
- The **isolated universe** removes repository peer skills. It measures what the
  target skill or underlying model provides without sibling-skill coverage.

Repository-mode parity can occur because a peer skill supplies the missing
behavior. It is therefore not proof of raw model capability and cannot by
itself justify removing or retiring the target skill. A capability review
should inspect both universes. If only one is run, the durable summary must
state the resulting limitation and must not answer the other universe's
question.

## Efficacy and marginal value

**Whole-skill efficacy** is the value of the complete current skill relative to
the no-skill baseline. **Component marginal value** is the change attributable
to one coherent section, example, reference, script, or asset when the
candidate is compared with the complete current skill.

These comparisons are not interchangeable:

- Whole-skill lift does not prove that every component contributes.
- A non-inferior reduced candidate can support removing or relocating a
  component even while the complete skill remains valuable.
- Baseline parity does not prove that the model has replaced the skill. The
  suite may be too easy, peers may supply coverage in the repository universe,
  or unique deterministic resources may be outside the measured cases.

Component decisions use coherent, reviewable boundaries. Individually safe
reductions must also pass as one combined candidate; marginal results are not
assumed to add independently.

## Evidence and gates

A capability review compares baseline, current, and candidate where each
condition uses fresh, equivalent fixtures and blinded judging. A context
reduction must satisfy all of these categories:

1. **Protected checks.** Safety, permission, and repository-contract behaviors
   designated as protected tolerate zero known regressions. An unknown result
   is not a pass, and average quality or context savings cannot compensate for
   a protected failure.
2. **Non-inferiority.** Candidate behavior must remain within an explicit,
   skill-appropriate margin of current behavior. Correctness, safety,
   triggering, cost, and evidence integrity stay separate; this contract does
   not set one universal margin.
3. **Complete-suite coverage.** The candidate must pass the relevant trigger and
   behavior suite, not only cases aimed at the proposed reduction.
4. **Required-profile coverage.** Every required profile must pass. Observed
   profiles inform the review without changing the support floor.
5. **Retained efficacy.** When the verdict keeps a skill, its justified value
   over baseline must remain visible rather than being inferred from
   candidate-versus-current parity alone.
6. **Evidence integrity.** Fixture fidelity, condition isolation, digests,
   judge blinding, missing results, and other limitations must be reported.

The review policy sets margins and minimum evidence for each skill. Missing
policy or materially uncertain evidence produces `insufficient-evidence`, not
an implicit approval.

The executable review reports correctness, safety, triggering, context, and
integrity independently in JSON, Markdown, and HTML. Protected `safety` and
`local-contract` checks use stable IDs and hard gates; any Candidate failure
fails the review, and unknown Current or Candidate evidence is
`insufficient-evidence`. Quality non-inferiority, retained Candidate lift over
Baseline, trigger recall and specificity, meaningful context reduction, fixture
fidelity and parity, judge blinding, complete-suite coverage, evidence coverage,
and minimum repeats each remain visible as their own gates. No aggregate
efficacy or efficiency score can override one of those outcomes.

### Repeats and held-back cases

Repeated runs expose stochastic variance and unstable improvements. Held-back
cases are not used to design the candidate and provide an overfitting check.
Both are required evidence for a durable reduction; a single run or only the
development cases cannot establish non-inferiority.

A suite in which baseline, current, and candidate all score at or near the
ceiling is **saturated**. Saturation triggers suite review: add or refine
discriminating, edge, and held-back cases before drawing a stronger conclusion.
It does not trigger automatic component removal or skill retirement.

## Durable summaries

Complete prompts, transcripts, event traces, command output, generated task
artifacts, workspaces, and temporary candidates remain local under ignored
evaluation storage. Only a bounded, reviewed summary may become durable
repository evidence.

That summary records:

- current, candidate, baseline configuration, evaluation, and runtime digests;
- exact task and judge models, runner and harness versions, and required or
  observed profile status;
- repository and isolated universe coverage plus development, repeated, and
  held-back case coverage;
- separate behavior, triggering, protected-check, context, cost, and integrity
  results;
- the configured margins, gate outcomes, uncertainty, limitations, and
  reproduction commands;
- the human-reviewed verdict and the reviewer rationale.

Summaries are evidence about one pinned comparison, not a timeless claim about
a model family or another harness.

## Verdict vocabulary

Every review ends with one of these bounded dispositions:

- `retain` — keep the component or skill unchanged because it has demonstrated
  value or reduction evidence does not justify a change.
- `compress` — preserve the behavior in shorter activation or discovery
  context.
- `move-to-reference` — keep the information as conditional context and load it
  only when needed.
- `replace-with-script` — preserve the behavior through a deterministic runtime
  operation with equivalent checks and availability.
- `remove-component` — delete a coherent component whose marginal value is not
  supported and whose removal passes every applicable gate.
- `merge-overlap` — consolidate duplicated value while preserving the required
  discovery, activation, and isolated-universe behavior.
- `retire` — withdraw the complete skill after satisfying the higher retirement
  bar below.
- `insufficient-evidence` — make no reduction because coverage, repeats,
  held-back cases, required profiles, integrity, or confidence are inadequate.

A verdict describes the reviewed evidence; it does not merge, publish, delete,
or otherwise apply a change automatically.

## Higher bar for retirement

Retirement removes discovery and activation paths as well as instructions, so
it requires more than component-level non-inferiority. A retirement proposal
must show all of the following:

1. Baseline is non-inferior to the complete current skill in the isolated
   universe across every required profile.
2. Repeated development, edge, and held-back cases are stable and do not merely
   show a saturated suite.
3. No protected behavior regresses, and unknown protected evidence is resolved.
4. Repository-universe parity is not supplied only by peer skills.
5. The skill has no unique scripts, assets, local policy, permissions, or
   deterministic operations whose value would be lost. Retirement remains
   possible only when equivalent value is deliberately preserved elsewhere and
   evaluated there.
6. Triggering and full-suite evidence show no important task population loses
   support.
7. A bounded capability summary documents uncertainty and receives explicit
   human review in a dedicated pull request.

Codex-only evidence can support a Codex-scoped conclusion. It cannot establish
retirement safety for other harnesses without corresponding runner evidence.
