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
- includes likely task contexts and artifacts;
- covers implicit intent, not just slash commands or exact names;
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
to exact wording.

## Behavior Evals

A behavior eval should describe a realistic prompt, inputs or fixtures,
expected behavior, and observable checks.

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

Review transcripts as well as final outputs. Useful symptoms include:

- too much exploration before finding the right procedure;
- ignored instructions;
- irrelevant references loaded too early;
- task variants confused with each other;
- missing validation despite a plausible final answer.

Aggregate repeated failures into design changes. Update the description,
resource split, instructions, examples, or scripts according to the
evidence.

## Iteration Loop

1. Design realistic test cases.
2. Run with the skill in a clean context.
3. Run a baseline when feasible.
4. Grade outputs against concrete assertions.
5. Inspect transcripts for process failures.
6. Revise the skill.
7. Re-run enough cases to confirm the change did not overfit.
