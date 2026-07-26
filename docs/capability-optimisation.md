# Capability optimisation

Capability optimisation asks whether every part of a skill still earns its
runtime cost as models and harnesses change. It complements corrective
improvement; it does not lower the evidence standard or turn the absence of a
known failure into proof that instructions are redundant.

This guide defines the repository contract for capability-review tooling. The
current evaluator compares baseline, current, and candidate packages, reports
context metrics, enforces repository-owned optimisation gates, and orchestrates
required and selected observed Codex model profiles across pinned review
inputs. `scripts/ablate_skill_components.py` uses that evidence to perform
component ablation through greedy backward elimination and a final combined
candidate rerun.

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

The executable profile contract lives at
[`eval-profiles.json`](../eval-profiles.json). Every required profile runs;
observed profiles are opt-in. Schema v1 requires every profile to use the same
top-level pinned judge model and protocol. The review command verifies the
Current, Candidate, eval, profile, case-group, judge-policy, harness-manifest,
and runner inputs across every profile/universe cell before aggregating gates.
Its eval digest covers the suite definition and fixture bytes, not prior
durable review exports.

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

The orchestrator runs both universes by default. A single-universe command is
invalid without an explicit limitation, keeping a narrower scope deliberate
and reviewable.

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

Repository-only `evals/<skill>/components.json` metadata defines those
boundaries. Schema version 1 selects an exact level 2-6 ATX heading in a
Markdown runtime file, assigns a stable component ID and class, and marks the
component protected or eligible. The selector must resolve exactly once inside
the skill package. Absolute paths, parent traversal, symlinks, non-Markdown
sources, missing or duplicate headings, level-1 headings, and overlapping or
nested component spans fail before evaluation. Heading-like lines inside
fenced code are not selectors. Exact matching deliberately turns heading drift
into a review stop instead of silently removing nearby prose.

`scripts/ablate_skill_components.py` implements greedy backward elimination.
For each round it creates a clean temporary candidate for every remaining
unprotected marginal removal, runs the existing required-profile capability
matrix in both repository and isolated universes, and chooses the approved
candidate with the strongest worst required-profile candidate-minus-current
quality delta, followed by incremental runtime-package byte savings. It
continues from that accepted reduction. If no marginal candidate is approved
with complete evidence, elimination stops. It then recreates and reruns the
combined candidate from the complete current runtime package.

Protected components are reported as `skipped-protected` and never enter a
candidate. By default, temporary packages and complete capability runs remain
under ignored `.skill-evals/` storage. An external `--output-root` is supported,
while repository-local output is accepted only below the ignored
`.skill-evals/` root. Temporary runtime candidates are always deleted. The
local `decision.json` retains current, component, eval, case-group, prior,
candidate, profile, and final digests; incremental and cumulative static
savings; quality deltas; hard regressions; gate outcomes; uncertainty; and
separate repository and isolated results. An accepted step is provisional
until the final combined rerun passes. The command does not rewrite prose,
apply the candidate, export a durable repository summary, commit a runtime
reduction, or promote it.

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
case labels record the intended separation between candidate design inputs and
the rest of the suite. The current orchestrator does not calculate
held-back-only metrics or per-group non-inferiority. Its quality and triggering
metrics remain whole-suite.

Case groups label a complete, non-overlapping partition of one unchanged eval
suite. The evaluator still runs the full suite in each matrix cell, while the
orchestrator records development and held-back group IDs and their repeat
counts. These labels are declarative process controls. A passing coverage gate
confirms that both labels were supplied and the full suite was repeated. It does
not prove held-back-only non-inferiority or measured group efficacy.

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
- repository and isolated universe coverage plus development and held-back
  partition labels and repeat counts;
- separate behavior, triggering, protected-check, context, cost, and integrity
  results;
- the configured margins, gate outcomes, uncertainty, limitations, and
  reproduction commands;
- the human-reviewed verdict and the reviewer rationale.

Summaries are evidence about one pinned comparison, not a timeless claim about
a model family or another harness.

Complete runs stay local under `.skill-evals/`. Opt-in JSON and Markdown
exports under `evals/<skill>/reviews/` are deterministic and size-bounded. They
are built from an allowlist and reject mutable model defaults; prompts,
transcripts, command output, generated artifacts, and workspace paths never
enter the durable form. A human reviewer must provide a bounded disposition
and rationale. The export records that automatic promotion is disabled.

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
  case-group process controls, required profiles, integrity, or confidence are
  inadequate.

A verdict describes the reviewed evidence; it does not merge, publish, delete,
or otherwise apply a change automatically.

## Higher bar for retirement

Retirement removes discovery and activation paths as well as instructions, so
it requires more than component-level non-inferiority. A retirement proposal
must show all of the following:

1. Baseline is non-inferior to the complete current skill in the isolated
   universe across every required profile.
2. Repeated whole-suite results are stable and do not merely show a saturated
   suite. Any held-back-only claim needs separate group-specific measurement.
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

## Capability Optimisation v1 pilot status

Issue #29 piloted the complete v1 workflow on `skill-architect` and the
safety-sensitive `commit` skill. The bounded summaries are stored with each
skill's repository-only reviews:

- [`skill-architect` pilot](../evals/skill-architect/reviews/issue-29-pilot.md)
- [`commit` pilot](../evals/commit/reviews/issue-29-pilot.md)

The completed issue #29 pilots demonstrated that:

- exact component metadata can bound a marginal review and prevent protected
  components from entering normal ablation candidates;
- required-profile reviews can run the complete suite with configured repeats,
  a declared development/held-back partition, and both repository and isolated
  skill universes;
- a smaller Candidate can remain blocked when evidence coverage is incomplete
  (`insufficient-evidence`) or other gates fail, even when its average behavior
  is close to Current;
- gate design rejects a Candidate when protected hard failures are present, and
  the commit pilot observed those failures alongside quality and coverage
  shortfalls even when isolated token evidence looked favorable; and
- rejected evidence retains Current and never applies, promotes, retires, or
  merges a runtime Candidate automatically.

The pilot did not prove a safe runtime reduction, so Capability Optimisation v1
remains unverified and its roadmap item stays open. It also did not establish
held-back-only efficacy, eliminate stochastic trigger and token variance, run
the observed frontier profile, or produce behavioral evidence for non-Codex
harnesses. Both summaries are agent-prepared and remain pending maintainer
review; they are not human approvals or retirement evidence. Complete prompts,
transcripts, command output, and workspaces remain local under ignored
`.skill-evals/` storage.
