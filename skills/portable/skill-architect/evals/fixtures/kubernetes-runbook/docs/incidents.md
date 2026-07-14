# Kubernetes Incident Response

Use this runbook for degraded production workloads. Require a configured
`kubectl` context and confirm the target cluster and namespace before any
state-changing command.

## Triage

1. Record the incident identifier, UTC start time, cluster, namespace, and
   affected workload.
2. Inspect workload status, recent events, rollout history, pod logs, and
   resource pressure.
3. Save collected evidence under `incidents/<incident-id>/` without
   modifying the cluster.
4. Summarize the likely failure mode and list evidence for and against it.

## Mitigation

- Prefer a documented rollback over ad hoc production edits.
- Show the exact mutation and request approval before executing it.
- Do not delete persistent volumes, namespaces, or unrecoverable data.
- If the cluster context, impact, or rollback target is ambiguous, stop
  and ask the incident commander.

## Verification

After mitigation, verify rollout health, readiness, error rate, and the
original user-visible symptom. Record commands, results, remaining risk,
and follow-up actions in the incident directory.
