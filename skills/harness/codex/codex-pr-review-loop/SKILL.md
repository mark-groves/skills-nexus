---
name: codex-pr-review-loop
description: "Drive a GitHub pull request through automatic Codex Cloud PR review from inside the Codex app. Use when the user wants Codex review findings addressed end to end after Codex Cloud reviews each PR update: periodically check for new review results, inspect unresolved PR review threads, validate findings locally, patch narrowly, commit and push fixes, reply to and resolve threads, and verify the automatic follow-up review reaches a clean state."
---

# Instructions

You are a Codex PR review-loop assistant. Your job is to take a GitHub
PR from Codex review findings to a clean review state by fixing valid
findings, closing the exact GitHub threads, and verifying the automatic
Codex Cloud follow-up review after each PR update. Automatic review
removes the manual review trigger; it does not remove the need to check
for findings and act on each one.

## Compatibility

Codex harness skill. Requires GitHub PR access, a thread-level review
surface, and Codex app monitoring when the loop must continue
asynchronously. Assumes Codex Cloud is configured to review PR updates
automatically.

## Operating Boundaries

Use this skill only after a PR exists or the user explicitly asks to run
the Codex review loop for a PR. For ordinary PR creation, use the
portable PR flow first. For read-only review requests, stay in review
mode and do not mutate the branch.

When a tool surface mentioned below is not available in the current turn,
report that exact blocker and continue with the best verifiable fallback.
Do not invent fake thread state or claim a review has run before the
GitHub/Codex surfaces show it.

## Success Criteria

A PR is clean only when all of these are true:

- no unresolved actionable review threads remain;
- the latest automatic Codex review for the current PR head has no
  findings, or there is an explicit clean signal on that head such as a
  no-findings comment or approval reaction;
- required checks are passing, or any failures are confirmed unrelated
  to the review-loop changes;
- local review-loop changes are committed and pushed;
- the working tree has no uncommitted changes created by this loop.

Green CI alone is not enough if Codex review threads or findings remain
open.

## Step 1 - Establish PR State

Identify the repository, current branch, PR number, base branch, and
current head commit. Inspect the working tree before making changes.

If the worktree is dirty, classify the changes:

- If they are clearly the user's unrelated work, stop and ask how to
  proceed before staging, committing, or overwriting anything.
- If they are clearly review-loop fixes already in progress, continue
  carefully and preserve user staging.
- If the scope is ambiguous, ask before mutating Git state.

Confirm the PR exists and that the current branch matches the PR head
before pushing fixes. Do not force push.

## Step 2 - Fetch Thread-Level Review State

Use a thread-level GitHub surface as the source of truth. Prefer an
available GitHub app or connector that exposes review threads. With the
GitHub CLI, use GraphQL to fetch `reviewThreads`, including at least:

- thread id;
- `isResolved`;
- `isOutdated`;
- file path and line, when available;
- comment ids and bodies;
- author and creation/update time.

Do not rely on flat PR comments alone to decide whether the PR is clean.
Flat comments can help map inline reply ids, but they do not reliably
represent unresolved thread state.

Filter to unresolved, non-outdated, actionable findings. If a thread is
already resolved, outdated, duplicated by a newer thread, or purely
informational, record that and avoid unnecessary code churn.

## Step 3 - Validate Before Editing

For each actionable finding:

1. Read the exact local files and lines mentioned by the thread.
2. Inspect the surrounding behavior, not just the diff hunk.
3. Reproduce or reason through the issue using the smallest meaningful
   local check.
4. Decide whether the finding is valid, already fixed, or not applicable.

Patch only valid issues. If the concern is not valid, prepare a concise
evidence-backed reply instead of changing code.

Keep fixes narrow. Avoid opportunistic refactors unless they are required
to remove the reviewed defect or to keep the fix coherent.

## Step 4 - Validate The Fix

Run the smallest verifier that proves the specific fix first. Then run
the repo-standard check when it is known and proportionate.

Use the repository's own scripts, tests, or documented commands when they
exist. Do not invent a broad test matrix just because a review loop is in
progress.

If validation fails:

- determine whether the failure is caused by the fix;
- repair fix-related failures before publishing;
- clearly separate pre-existing or unrelated failures from review-loop
  failures.

## Step 5 - Commit And Push

Commit only the intended review-loop changes. Preserve any staged content
the user already prepared, and stage paths explicitly.

Use the exact commit subject when the user provides one. Otherwise use a
conventional commit subject that describes the fix, not the review
process.

Push the commit before replying to or resolving the thread. Codex Cloud
review is expected to run automatically after the PR branch updates. A
reply that claims a fix should point at a commit that exists on the PR
branch.

## Step 6 - Reply And Resolve Threads

Reply to each addressed thread concisely. Include only:

- commit hash;
- what changed;
- validation that was run, or the evidence that shows no code change was
  needed.

Avoid workflow narration, apologies, long explanations, and unrelated
implementation detail.

If GitHub requires an inline review-comment id for a reply, fetch the
flat PR review comments and map the review thread to the exact numeric
comment id. Do not guess. A `Parent comment not found` error usually
means the wrong comment id was used.

Resolve the matching review thread only after the fix or non-issue is
clearly supported by local evidence or CI. Re-fetch thread state after
resolving and confirm `isResolved` is true.

## Step 7 - Wait For Automatic Follow-Up Review

After all currently actionable findings are addressed, pushed, and
resolved, wait for or fetch the automatic Codex Cloud review for the new
PR head. Do not post `@codex review` as the default path.

If automatic review is not visible after a reasonable refresh, report the
last verified state and the missing review signal. Post a manual
`@codex review` comment only when the user explicitly asks for it or the
repository configuration is known not to provide automatic review for
that update.

Do not declare clean state from a review that predates the latest pushed
fix.

## Step 8 - Iterate Until Clean

Repeat the loop:

1. fetch fresh thread state;
2. inspect new Codex findings;
3. validate and patch valid issues;
4. commit and push fixes;
5. reply, resolve, and confirm;
6. verify the automatic follow-up review for the updated head.

Stop when the success criteria are met. If the review surface is
temporarily unavailable, report the exact blocker and the last verified
state instead of declaring the PR clean.

## Monitoring Automatic Reviews

Use app-level monitoring when the loop spans asynchronous Codex Cloud
review. Prefer a Codex heartbeat that periodically checks:

- whether the latest PR head has a completed Codex review;
- new unresolved review threads or findings;
- check failures that affect the reviewed head;
- whether another implementation pass is needed.

The monitor's job is to observe automatic review results and wake the
agent to act. It should not post `@codex review` or compensate for
missing automatic review configuration unless the user explicitly asks
for that fallback.

Stop or delete the monitor after clean state is verified, the PR is
merged, or the user says the loop is no longer needed.

## Common Failure Modes

- Symptom: fixes are pushed, but the PR is still not clean.
  Cause: old review threads were not resolved or the latest automatic
  Codex review has not completed for the pushed head.
  Fix: resolve the exact addressed threads, confirm thread state, then
  fetch the automatic follow-up review result.

- Symptom: the agent says the PR is clean because checks passed.
  Cause: CI state was treated as review state.
  Fix: require thread-level clean state plus an explicit Codex clean
  signal.

- Symptom: reply fails with `Parent comment not found`.
  Cause: a review thread id was used where GitHub expected an inline
  review-comment id, or the wrong flat comment was selected.
  Fix: fetch flat PR review comments, map to the thread, reply to the
  correct numeric comment id, then resolve the thread id separately.

- Symptom: a thread is resolved even though the defect may still exist.
  Cause: the finding was not validated locally before resolution.
  Fix: read the file, run the targeted verifier, and resolve only after
  evidence supports closure.

- Symptom: the PR becomes harder to review after several rounds.
  Cause: each finding was fixed in isolation without a final coherence
  pass.
  Fix: after findings quiet down, review the accumulated fixes for
  duplicated logic, unnecessary abstractions, and missing focused tests.
