# Eval retirement inventory

Verified against repository paths at planning time. Actions are Phase A unless
marked later.

Legend

- DELETE. Remove in Phase A.
- KEEP. Leave in place.
- REWRITE. Edit in Phase A so static checks stay green.
- LATER. Architecture track after Phase A.
- QUARANTINE. Codex pilot scrap under `evals/`. Move or delete in Phase A.

## KEEP (static floor, packaging, observation, cases)

| Path | Role |
| --- | --- |
| `scripts/validate_repo.py` | Static repo contract. Retarget imports after catalog extract. |
| `scripts/check-skills.sh` | Wraps validate_repo. |
| `scripts/check-quality.sh` | Ruff, format, mypy, ShellCheck, actionlint, bandit, zizmor. |
| `.github/workflows/ci.yml` | Quality and skills jobs. No live eval. |
| `plugins/` | Agent Plugin bundles. |
| `scripts/package_skill.py` | Runtime packaging. Uses catalog helpers. |
| `scripts/plugin_repository.py` | Plugin discovery. |
| `scripts/deploy-skills.sh` | Install by harness stem. |
| `scripts/record_observation.py` | Observation capture. |
| `scripts/redact_observation.py` | Redaction. |
| `scripts/classify_observation.py` | Classification. |
| `scripts/promote_observation.py` | Promote into `evals.json`. Needs thin loader. |
| `scripts/reject_observation.py` | Reject path. |
| `scripts/skill_observation/` | Observation library. |
| `scripts/skill_triage/` | Triage library. Needs thin loader. |
| `harnesses/agents.json` | Install roots. |
| `harnesses/claude-code.json` | Install roots. |
| `harnesses/copilot.json` | Install roots. |
| `harnesses/cursor.json` | Install roots. |
| `harnesses/kiro.json` | Install roots. |
| `evals/*/evals.json` | Trigger and behavior cases. |
| `evals/*/fixtures/` | Fixtures. |
| `evals/*/components.json` | Component maps. Data kept. Live ablation goes away. |
| `evals/*/capability-case-groups.json` | Case groups. Data kept. |
| `evals/*/routine-screen.json` | Routine screen contracts. Data kept. |
| `evals/*/*.md` case notes | Harness-neutral fixture descriptions. |
| `schemas/skill-observation-*.schema.json` | Observation schemas. |
| `schemas/agent-plugins-plugin-1.0.0.schema.json` | Plugin schema. |
| `schemas/skill-components-v1.schema.json` | Components schema. |
| `schemas/routine-screen-v1.schema.json` | Routine screen schema. |
| `docs/development.md` | Local static commands. |
| `docs/authoring-skills.md` | Authoring guide. |

## DELETE (Codex live matrix and CapOpt runners)

| Path | Role |
| --- | --- |
| `scripts/eval_skills.py` | Live matrix CLI. |
| `scripts/skill_eval/codex_runner.py` | Codex process runner. |
| `scripts/skill_eval/adapters/codex.py` | Codex adapter. |
| `scripts/skill_eval/adapters/registry.py` | Adapter registry (Codex builtins). |
| `scripts/skill_eval/adapters/events.py` | Codex event parse. |
| `scripts/skill_eval/engine.py` | Live task engine. |
| `scripts/skill_eval/judging.py` | Live blind judge glue. |
| `scripts/skill_eval/report.py` | Live report writer. |
| `scripts/skill_eval/sandbox.py` | Podman sandbox for live runs. |
| `scripts/skill_eval/harness.py` | Live harness protocols. |
| `scripts/skill_eval/evidence.py` | Live evidence bundle. |
| `scripts/probe_cursor_eval.py` | Cursor CLI probe for the closed multi-harness track. |
| `scripts/review_skill_capability.py` | Live CapOpt review CLI. |
| `scripts/ablate_skill_components.py` | Live ablation CLI. |
| `scripts/skill_review/` | CapOpt orchestration library. |
| `harnesses/codex.json` | Codex install roots. Mark will not use Codex. |
| `.codex` | Empty Codex marker file. |
| `eval-profiles.json` | Codex-only model profiles. |
| `schemas/eval-profiles-v1.schema.json` | Profile schema. |
| `schemas/eval-profiles-v2.schema.json` | Profile schema. |
| `tests/test_eval_skills.py` | Live eval tests (after static cases move or drop). |
| `tests/test_harness_boundary.py` | Live harness boundary tests. |
| `tests/test_probe_cursor_eval.py` | Cursor probe tests. |
| `tests/test_review_skill_capability.py` | CapOpt review tests. |
| `tests/test_component_ablation.py` | Ablation tests. |
| `tests/test_podman_sandbox.py` | Sandbox tests. |
| `docs/sandbox-runner.md` | Live sandbox runner doc. |

## REWRITE (Phase A)

| Path | Why |
| --- | --- |
| `scripts/skill_eval/core.py` | Extract thin `evals.json` loader and skill resolve into `scripts/eval_cases.py` (or keep a core-only module). Drop live-only helpers. |
| `scripts/skill_eval/__init__.py` | Re-export only survivors, or delete package once callers move. |
| `scripts/validate_repo.py` | Drop `codex` from `REQUIRED_HARNESSES`. Drop eval-profiles validation. Import thin loader. Keep evals.json and remaining harness checks. Keep optional components / case-group / routine-screen loaders only if those files stay validated without `skill_review` live code. |
| `tests/test_validate_repo.py` | Remove Codex profile fixtures. Keep evals and harness assertions for remaining harnesses. |
| Observation tests with Codex profile samples | Strip Codex profile assumptions. Keep `"harness": "codex"` as free text in old fixtures only if still meaningful, or rewrite samples to `cursor`. |
| `README.md` | Remove live Codex eval instructions. Point prove path at the ADR and future playbook. |
| `AGENTS.md` | Remove Codex CLI requirement for live eval. |
| `ROADMAP.md` | State Codex removed. Point prove path at Cloud Agent ADR. |
| `docs/evaluating-skills.md` | Rewrite around Cloud Agent orchestration. |
| `docs/capability-optimisation.md` | Retire Codex CapOpt live path. Keep gate vocabulary only where still useful. |
| `docs/continuous-improvement.md` | Remove live matrix steps. Keep observe → triage → promote. |
| `docs/deployment.md` | Remove Codex as an install target if the harness file is deleted. |
| `docs/cursor-evaluation-adapter.md` | Mark historical. CLI production path stays closed. |

## QUARANTINE under `evals/`

Harness-neutral case data stays. Codex pilot writeups go.

| Path | Action |
| --- | --- |
| `evals/cloud-diagram/` | KEEP cases and companions. |
| `evals/commit/` evals, fixtures, components, groups, routine screen, case markdown | KEEP. |
| `evals/drawio-shapes/` | KEEP. |
| `evals/pr/` | KEEP. |
| `evals/skill-architect/` evals, fixtures, components, groups, routine screen | KEEP. |
| `evals/commit/reviews/issue-29-pilot.md` | QUARANTINE. Codex pilot scrap. |
| `evals/skill-architect/reviews/issue-29-pilot.md` | QUARANTINE. |
| `evals/skill-architect/reviews/issue-39-sources-rerun.md` | QUARANTINE. |
| `evals/skill-architect/fixtures/capability-review/eval-profiles.json` | QUARANTINE or rewrite. Codex profile fixture. |

`review_policy` blocks inside live `evals.json` files are optional today. Phase A may leave them as dormant checklist data or drop them once nothing executes them. Do not treat them as a live matrix.

## Coupling that blocks naive delete

1. `validate_repo.py` imports `skill_eval.core` (`EvalError`, `load_eval_spec`, `resolve_skill`).
2. `promote_observation.py` / `skill_triage` import `load_eval_spec`.
3. `record_observation.py` imports `resolve_skill` / discovery helpers.
4. `package_skill.py` imports runtime copy helpers from the eval package.
5. `REQUIRED_HARNESSES` includes `codex`.
6. `eval-profiles.json` is validated today.
7. Optional eval companions currently load through `skill_review` static loaders. Preserve those loaders or inline them before deleting `scripts/skill_review/`.

## Phase A proof commands

```bash
bash scripts/check-quality.sh
bash scripts/check-skills.sh
python -m pytest tests/ -q
```

Live Codex matrices are not part of the floor.

## LATER (architecture track, not Phase A code)

| Item | Notes |
| --- | --- |
| `docs/eval-orchestration.md` | Playbook modes and blinding. |
| `docs/eval-types/*.schema.json` | Six domain schemas. |
| Pure evidence fold helper | Parse and summarize run artifacts. No spawn. |
| Issue #74 runner automation | Out of scope until contract schemas land. |
| CapOpt swarm replacement | Data kept. New prove path comes later. |
