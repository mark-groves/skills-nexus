# Evaluating skills

The static floor is the merge gate. Behavioral proof is a Cloud Agent
prove path, not a Python live matrix.

```text
plugins/<bundle>/skills/<name>/   runtime skill package
evals/<name>/evals.json           trigger and behavior cases
evals/<name>/fixtures/            repository-only scenario inputs
scripts/eval_cases.py             thin catalog and companion loaders
```

`evals.json` stays harness-neutral. `validate_repo` loads it through
`load_eval_spec`. Observation promote uses the same loader. Packaged skills
never include `evals/`.

## Static floor

```bash
bash scripts/check-quality.sh
bash scripts/check-skills.sh
python -m pytest tests/ -q
```

Those commands parse catalogs, harness manifests, and companion files. They do
not spawn agents.

Optional companions under `evals/<skill>/` still validate when present:

- `components.json`
- `capability-case-groups.json`
- `routine-screen.json`

`review_policy` blocks inside `evals.json` stay as dormant checklist data.

## Prove path

Orchestration lives in the
[Cloud Agent eval playbook](eval-orchestration.md). It does not live in a
second Python matrix. The decision record is
[ADR 0001](adr/0001-cloud-agent-eval-orchestration.md). Domain schemas live
in `docs/eval-types/`.

`HarnessTarget` is `cursor-cloud-agent` only. Codex live runners, eval
profiles, and the Codex deploy harness are gone.

A prove-variant compares current versus candidate with one organic prompt,
blinded arena workers, one blinded judge, and a human `EvidenceSummary`.
`scripts/eval_evidence.py` emits, admits, and summarizes artifacts. It does
not spawn agents. Chats alone cannot go green. Named limits are in the ADR.
The first rehearsal is
`evals/commit/reviews/prove-variant-draft-message.json`.

## Capture and promote

Record a bounded observation, redact it, classify it, then promote a
reproducible case into `evals.json` or reject it. See
[Continuous improvement](continuous-improvement.md).

The Cursor CLI production adapter stays closed. The historical probe writeup
is [Cursor evaluation adapter](cursor-evaluation-adapter.md).
