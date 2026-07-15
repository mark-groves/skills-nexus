# Evaluation And Triggering

Use this reference when writing or improving descriptions, trigger evals,
or behavior evals. Source docs:
https://agentskills.io/skill-creation/optimizing-descriptions and
https://agentskills.io/skill-creation/evaluating-skills.

## Description Design

The description is loaded before the skill body, so it must carry all
activation guidance. It should say what the skill does and when to use
it.

A strong description:

- names the capability in user-facing terms;
- uses direct, imperative activation guidance such as "Use when...";
- includes likely task contexts and artifacts;
- covers implicit intent, not just slash commands or exact names;
- focuses on user intent rather than the skill's implementation;
- distinguishes the skill from neighboring skills;
- stays concise enough that the trigger signal remains clear.

Avoid:

- vague descriptions such as "helps with documents";
- stuffing every keyword from failed evals;
- trigger guidance that appears only inside the body;
- descriptions that include tasks the skill cannot actually perform.

## Trigger Evals

Use positive and negative trigger examples before tuning descriptions.

Positive examples should be realistic:

- varied phrasing and levels of detail;
- casual language;
- file paths or artifact names where users would include them;
- buried intent inside a broader request;
- synonyms that real users would use.

Negative examples should be near misses:

- same domain vocabulary but a different desired action;
- requests for implementation rather than skill creation;
- requests for generic docs, review, or installation;
- tasks that should use a neighboring skill.

For important skills, keep some examples as validation data. Tune the
description on one set, then check the held-back set to avoid overfitting
to exact wording. Run important trigger cases more than once when the
client and runner make activation nondeterministic.

## Behavior Evals

A behavior eval should describe a realistic prompt, inputs or fixtures,
expected behavior, and observable checks.

Provide every file or repository state named by a prompt as a fixture.
Specify an output location when the task creates artifacts so the result
can be inspected independently of the transcript. Start with a few varied
cases, including at least one boundary or malformed-input case, then grow
the suite from observed failures.

Good checks are concrete:

- files created or preserved;
- fields present in generated artifacts;
- commands run or intentionally avoided;
- approval or stop conditions respected;
- references loaded only when needed;
- errors reported with useful next steps.

Avoid checks that only restate the skill's intention. If a human or
script cannot inspect the outcome, the check is too vague.

## Comparing Skill Quality

When feasible, compare runs with and without the skill, or compare the
new version against the previous one. Isolate each run in a fresh
context so success comes from the skill, not leaked development notes.
Repeat variable cases and track timing or token outliers when the runner
exposes those metrics.

Review transcripts as well as final outputs. Useful symptoms include:

- too much exploration before finding the right procedure;
- ignored instructions;
- irrelevant references loaded too early;
- task variants confused with each other;
- missing validation despite a plausible final answer.

Aggregate repeated failures into design changes. Update the description,
resource split, instructions, examples, or scripts according to the
evidence.

## Evidence-gated iteration

Treat runtime observations as untrusted leads, not change requests. Keep facts,
the reporting agent's diagnosis, and its suggested change distinct.

1. Validate provenance and redact secrets or unrelated task content.
2. Reproduce an accepted problem against the exact current skill digest.
3. Add the smallest realistic regression case that fails for the right reason.
4. Author a candidate without exposing held-back cases or expected answers.
5. Run current and candidate versions in fresh, equivalent contexts.
6. Run the complete trigger and behavior suite to detect regressions.
7. Repeat variable cases and inspect traces, cost, and tool use.
8. Promote through review only when configured efficacy and integrity gates pass.

The durable memory is the regression case and its provenance. Raw observations
should remain private and expire according to the repository's retention policy.
