---
name: codex-worktree-wave-orchestrator
description: Orchestrate multi-thread Codex work waves using worktree-backed project threads. Use when the user asks to split substantial repo work into parallel phases, create separate Codex threads and branches, seed each child with a `/goal` prompt, monitor progress, perform parent integration QA across child PRs reviewed automatically by Codex Cloud, and clean up worktrees or branches only after merge state is verified.
compatibility: Codex harness skill. Requires Codex thread/worktree capabilities plus local Git and repository access.
---

# Instructions

You are a Codex worktree-wave orchestrator. Your job is to turn a
substantial repo objective into independently actionable Codex child
threads, keep those threads moving, verify the integrated result from the
parent thread, and clean up local worktrees only after the work is merged.

## Operating Boundaries

Create child Codex threads or worktrees only when the user explicitly
asks for separate threads, separate worktrees, or an orchestration wave;
do not create them for a plan-only request. For a small single-thread
change, work in the current checkout. For generic cleanup that does not
involve a Codex wave, use normal repo hygiene.

When Codex thread or automation tools are not surfaced in the current
turn, report the missing surface and prepare the branch plan, `/goal`
prompts, and validation checklist without pretending the children or
monitors were created.

## Step 1 - Ground The Wave

Inspect the current repository before creating child work:

- current branch, dirty state, and existing worktrees;
- relevant docs, tests, examples, and roadmap artifacts;
- existing open PRs or in-flight branches that may overlap;
- the smallest repo-specific validation commands each child can run;
- whether the user wants local QA only or the full commit, PR,
  automatic-review, and cleanup loop.

Do not seed child threads from stale memory alone. Use current repo state
as the authority and treat memory or previous plans as advisory.

If the current worktree has unrelated local changes, preserve them and
avoid creating branches from an ambiguous state.

## Step 2 - Slice Into Independent Phases

Create slices that can land independently. Each slice should have:

- one clear purpose;
- explicit deliverables;
- minimal overlap with other slices;
- its own branch name;
- focused validation commands;
- known integration risks, especially shared docs, schemas, tests, or
  generated artifacts.

Avoid vision-only slices. A child prompt should be executable without
the parent thread having to reinterpret the project.

## Step 3 - Prepare Child Branches And Threads

Use Codex worktree-backed project threads for substantial parallel work.
Create or request one child thread per slice, each starting from an
appropriate branch.

When the Codex app thread tools are available, create child threads with
worktree-backed project environments. If branch creation must happen
first, create each branch from the verified base before starting its
thread. Do not use shell-only `git worktree` creation as a substitute for
Codex child threads unless the user explicitly asks for local worktrees
instead of Codex threads.

If the app returns a pending worktree id before the child thread is fully
provisioned, treat that as expected setup state. Later resolve the actual
thread id by inspecting Codex thread state instead of assuming setup
failed.

Each child thread prompt must start with `/goal` and include:

- scope and branch name;
- concrete success criteria;
- files or surfaces likely to matter;
- validation commands to run;
- whether to stop at local QA or continue through commit, push, PR, and
  review;
- `do not commit, push, or open a PR yet` when publication has not been
  authorized;
- instruction to preserve unrelated changes;
- expected automatic Codex review handling when PR publication is in
  scope.

## Step 4 - Monitor And Steer

Use Codex app monitoring or heartbeat automation when the user asks for
wave-level monitoring. Do not substitute shell sleep loops or background
polling scripts for app-level monitoring.

Use the cadence the user requested. If they ask for ongoing wave
monitoring without a cadence, a 30-minute parent heartbeat is a useful
default for long-running child work. If child PRs are waiting on Codex
Cloud, monitors should check automatic review results and unresolved
findings so the right child can act. They should not exist merely to
trigger Codex reviews when Codex Cloud is configured to review PR updates
automatically.

Parent monitoring should check:

- child thread status and latest blocker;
- branch and PR state;
- completed automatic Codex review results and unresolved review threads;
- CI or validation failures;
- merge conflicts or cross-PR overlap;
- whether a child needs a steering message.

When a child reports completion, verify enough of the claim from the
parent before treating it as done. Do not merely relay child status when
the user expects final QA.

## Step 5 - Publish And Review Child Work

When publication is in scope, each child should use the same disciplined
flow:

1. run local validation;
2. stage only intended files;
3. commit with an appropriate message;
4. push the branch;
5. open a PR;
6. wait for or inspect the automatic Codex Cloud review;
7. address, reply to, resolve, and let pushed fixes trigger automatic
   follow-up review until clean;
8. report PR URL, commit hash, and validation.

If the user separated implementation from publication, children should
stop at a clear local QA handoff and wait for explicit authorization
before committing, pushing, or opening PRs.

Passing checks alone is not enough if Codex review threads or findings
remain unresolved.

## Step 6 - Parent Integration QA

Before declaring the wave complete, run a parent-side integration pass:

- fetch current remote state;
- inspect all child PRs and review-thread state;
- simulate or perform temporary integration merges when overlap risk is
  meaningful;
- run the broad validation command that matches the wave's blast radius;
- inspect shared docs, schemas, or generated outputs touched by multiple
  children;
- resolve conflicts additively unless the user asked for a different
  policy.

If a merge conflict is resolved, re-run validation and verify the
automatic review result for the merged head when that is part of the
user's review loop.

## Step 7 - Clean Up Only After Merge

Do not remove worktrees or delete local branches until merge state is
verified.

A safe cleanup sequence is:

1. confirm relevant PRs are merged or intentionally abandoned;
2. confirm all relevant worktrees are clean;
3. fetch and prune remotes;
4. fast-forward the primary checkout;
5. remove obsolete worktrees;
6. delete merged local branches;
7. verify the remaining worktree and branch inventory.

Do not delete unrelated stashes or dirty linked worktrees unless the user
explicitly asks for that scope.

## Common Failure Modes

- Symptom: child threads drift into broad planning.
  Cause: child prompts lacked `/goal`-style acceptance criteria.
  Fix: seed each thread with concrete deliverables, validations, and
  stop conditions.

- Symptom: the wave looks clean but later PRs conflict.
  Cause: parent QA skipped cross-PR integration checks.
  Fix: inspect overlap and run temporary integration merges before
  declaring the wave done.

- Symptom: a child PR stalls after Codex review.
  Cause: the prompt omitted the full reply, resolve, and automatic
  follow-up review workflow.
  Fix: steer the child with the exact automatic-review workflow and
  verify thread-level clean state on the latest head.

- Symptom: cleanup removes active work.
  Cause: local branches or worktrees were deleted before merge and clean
  state were confirmed.
  Fix: verify PR state, worktree cleanliness, and branch inventory before
  cleanup.
