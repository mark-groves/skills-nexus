import contextlib
import io
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "scripts"))

import review_skill_capability  # noqa: E402
from skill_eval.core import (  # noqa: E402
    RUNTIME_EXCLUDED_NAMES,
    EvalError,
    load_eval_spec,
    stable_digest,
)
from skill_review.core import (  # noqa: E402
    CapabilityReviewConfig,
    RoutineScreenConfig,
    build_durable_summary,
    export_durable_summary,
    load_case_groups,
    load_profile_contract,
    load_routine_screen_contract,
    run_capability_review,
    run_routine_screen,
    select_profiles,
    validate_routine_escalation,
    validate_universes,
)


class CapabilityReviewFixture:
    def __init__(self, root: Path) -> None:
        self.repo = root / "repo"
        self.repo.mkdir()
        self.skill = self.repo / "skills" / "demo"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Current demo\n---\n# Current\n",
            encoding="utf-8",
        )
        self.candidate = root / "candidate"
        self.candidate.mkdir()
        (self.candidate / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Candidate demo\n---\n# Candidate\n",
            encoding="utf-8",
        )
        eval_dir = self.repo / "evals" / "demo"
        eval_dir.mkdir(parents=True)
        self.eval_path = eval_dir / "evals.json"
        self.eval_path.write_text(
            json.dumps(
                {
                    "skill_name": "demo",
                    "trigger_evals": [
                        {"id": 1, "query": "development trigger", "should_trigger": True},
                        {"id": 2, "query": "held-back trigger", "should_trigger": False},
                        {"id": 3, "query": "development near miss", "should_trigger": False},
                    ],
                    "behavior_evals": [
                        {
                            "id": 1,
                            "prompt": "DEVELOPMENT PROMPT MUST NOT EXPORT",
                            "expected_behavior": "development",
                            "fixtures": [],
                            "checks": ["development check"],
                        },
                        {
                            "id": 2,
                            "prompt": "HELD BACK PROMPT MUST NOT EXPORT",
                            "expected_behavior": "held back",
                            "fixtures": [],
                            "checks": ["held-back check"],
                        },
                        {
                            "id": 3,
                            "prompt": "SECOND DEVELOPMENT PROMPT MUST NOT EXPORT",
                            "expected_behavior": "second development",
                            "fixtures": [],
                            "checks": [
                                {
                                    "id": "development-safety",
                                    "text": "development safety check",
                                    "class": "safety",
                                    "gate": "hard",
                                }
                            ],
                        },
                    ],
                    "review_policy": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        harness_dir = self.repo / "harnesses"
        harness_dir.mkdir()
        (harness_dir / "codex.json").write_text(
            '{"project_install_root": ".codex/skills", "user_install_root": "~/.codex/skills"}\n',
            encoding="utf-8",
        )
        self.profiles = self.repo / "eval-profiles.json"
        self.profiles.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "judge_policy": {
                        "id": "fake-policy-v1",
                        "model": "fake-judge-v1",
                        "protocol": "skill-eval-candidate-v3-condition-blind",
                    },
                    "profiles": [
                        {
                            "id": "fake-required",
                            "adapter": "codex",
                            "model": "fake-task-v1",
                            "judge_model": "fake-judge-v1",
                            "required": True,
                        },
                        {
                            "id": "fake-observed",
                            "adapter": "codex",
                            "model": "fake-task-v2",
                            "judge_model": "fake-judge-v1",
                            "required": False,
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.case_groups = self.repo / "evals" / "demo" / "capability-case-groups.json"
        self.case_groups.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "groups": [
                        {
                            "id": "development",
                            "kind": "development",
                            "trigger_cases": [1, 3],
                            "behavior_cases": [1, 3],
                        },
                        {
                            "id": "held-back-v1",
                            "kind": "held-back",
                            "trigger_cases": [2],
                            "behavior_cases": [2],
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.routine_contract = self.repo / "evals" / "demo" / "routine-screen.json"
        self.routine_contract.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "trigger_cases": [1, 3],
                    "behavior_cases": [1, 3],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.output = root / "local-evidence"

    def config(
        self,
        *,
        include_observed: bool = True,
        universes: tuple[str, ...] = ("repository", "isolated"),
    ) -> CapabilityReviewConfig:
        contract = load_profile_contract(self.profiles)
        profiles = select_profiles(
            contract,
            ["fake-observed"] if include_observed else [],
            include_all_observed=False,
        )
        spec = load_eval_spec(self.skill, self.repo / "evals")
        groups = load_case_groups(self.case_groups, spec)
        return CapabilityReviewConfig(
            repo_root=self.repo,
            skill="demo",
            candidate=self.candidate,
            profile_source=self.profiles,
            contract=contract,
            profiles=profiles,
            case_group_source=self.case_groups,
            case_groups=groups,
            universes=universes,
            universe_limitation=None,
            trigger_repeats=2,
            behavior_repeats=2,
            activation_threshold=0.5,
            jobs=1,
            timeout=10,
            codex_binary="fake-codex",
            sandbox="workspace-write",
            allow_fixture_scripts=True,
            output_root=self.output,
        )

    def routine_config(self) -> RoutineScreenConfig:
        review = replace(
            self.config(include_observed=False),
            trigger_repeats=1,
            behavior_repeats=1,
            jobs=2,
        )
        spec = load_eval_spec(self.skill, self.repo / "evals")
        return RoutineScreenConfig(
            review=review,
            contract_source=self.routine_contract,
            contract=load_routine_screen_contract(
                self.routine_contract,
                spec,
                review.case_groups,
            ),
        )


class FakeEvaluationRunner:
    def __init__(self, *, required_verdict: str = "approved") -> None:
        self.required_verdict = required_verdict
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, args: Any) -> tuple[dict[str, Any], Path]:
        self.calls.append((args.model, args.judge_model, args.skill_universe))
        repo_root = args.repo_root.resolve()
        skill_dir = repo_root / "skills" / "demo"
        candidate_dir = args.candidate.resolve()
        eval_path = repo_root / "evals" / "demo" / "evals.json"
        verdict = self.required_verdict
        if args.model == "fake-task-v2" and args.skill_universe == "isolated":
            verdict = "rejected"
        approved = verdict == "approved"
        status = "pass" if approved else "fail"
        run_dir = args.output_root / "demo" / "fake-run"
        run_dir.mkdir(parents=True)
        condition_grade = {
            "total": 4,
            "passed": 4 if approved else 3,
            "failed": 0 if approved else 1,
            "unknown": 0,
            "pass_rate": 1.0 if approved else 0.75,
            "evidence_coverage": 1.0,
        }
        efficiency = {
            "completed_runs": 4,
            "failed_runs": 0,
            "median_duration_seconds": 0.01,
            "input_tokens": 40,
            "output_tokens": 20,
            "total_tokens": 60,
            "median_tokens": 15,
            "tool_calls": 0,
        }
        footprint = {
            "description": {"characters": 10, "utf8_bytes": 10},
            "skill_md_body": {"characters": 20, "utf8_bytes": 20},
            "runtime_package": {
                "file_count": 1,
                "bytes": 50,
                "digest_sha256": "a" * 64,
            },
        }
        result: dict[str, Any] = {
            "schema_version": 3,
            "skill": {
                "name": "demo",
                "path": str(skill_dir),
                "eval_path": str(eval_path.parent),
                "runtime_digest_sha256": stable_digest(
                    skill_dir,
                    exclude=RUNTIME_EXCLUDED_NAMES,
                ),
                "eval_spec_digest_sha256": stable_digest(eval_path),
            },
            "candidate": {
                "name": "demo",
                "path": str(candidate_dir),
                "runtime_digest_sha256": stable_digest(
                    candidate_dir,
                    exclude=RUNTIME_EXCLUDED_NAMES,
                ),
            },
            "runtime": {
                "adapter": "codex",
                "codex_version": "fake-codex 1.0",
                "model": args.model,
                "judge_model": args.judge_model,
                "skill_universe": args.skill_universe,
            },
            "trigger": {
                "summary": {
                    "total": 4,
                    "completed": 4,
                    "correct": 4,
                    "accuracy": 1.0,
                    "recall": 1.0,
                    "specificity": 1.0,
                    "activation_rate": 0.5,
                    "run_errors": 0,
                }
            },
            "candidate_trigger": {
                "summary": {
                    "total": 4,
                    "completed": 4,
                    "correct": 4,
                    "accuracy": 1.0,
                    "recall": 1.0,
                    "specificity": 1.0,
                    "activation_rate": 0.5,
                    "run_errors": 0,
                }
            },
            "behavior": {
                "summary": {
                    "skill": condition_grade,
                    "baseline": condition_grade,
                    "candidate": condition_grade,
                    "case_pass_rate": {
                        "skill": 1.0,
                        "baseline": 1.0,
                        "candidate": 1.0 if approved else 0.5,
                        "graded_cases": 4,
                    },
                    "efficiency": {
                        "skill": efficiency,
                        "baseline": efficiency,
                        "candidate": efficiency,
                    },
                }
            },
            "context_footprint": {
                "skill": footprint,
                "baseline": {
                    "description": {"characters": 0, "utf8_bytes": 0},
                    "skill_md_body": {"characters": 0, "utf8_bytes": 0},
                    "runtime_package": {
                        "file_count": 0,
                        "bytes": 0,
                        "digest_sha256": None,
                    },
                },
                "candidate": footprint,
            },
            "candidate_comparison": {
                "sign_convention": {
                    "quality": "candidate minus comparison",
                    "reduction": "current minus candidate",
                },
                "candidate_minus_current_quality": 0.0 if approved else -0.25,
                "candidate_minus_current_quality_percentage_points": (0.0 if approved else -25.0),
                "candidate_lift_over_baseline": 0.1,
                "candidate_lift_over_baseline_percentage_points": 10.0,
                "static_reductions": {"skill_md_body_characters": 10},
                "dynamic_input_token_reduction": 4,
                "paired_checks": {
                    "wins": 0,
                    "regressions": 0 if approved else 1,
                    "ties": 4,
                    "unknown": 0,
                },
            },
            "optimisation_review": {
                "verdict": verdict,
                "approved": approved,
                "hard_failure": not approved,
                "hard_blocked": not approved,
                "dimensions": {
                    "correctness": {
                        "status": status,
                        "gates": [
                            {
                                "id": "fake-gate",
                                "status": status,
                                "hard": True,
                                "observed": 1 if approved else 0,
                                "required": 1,
                                "detail": "not exported",
                            }
                        ],
                    }
                },
                "no_aggregate_override": True,
            },
            "prompt": "RAW PROMPT MUST NOT EXPORT",
            "workspace": str(run_dir / "workspace"),
            "command_output": "RAW COMMAND OUTPUT MUST NOT EXPORT",
        }
        (run_dir / "results.json").write_text(
            json.dumps(result) + "\n",
            encoding="utf-8",
        )
        return result, run_dir


class RoutineEvaluationRunner(FakeEvaluationRunner):
    """Produce filtered, single-repeat gates without external model calls."""

    def __init__(self, *, failure: str | None = None) -> None:
        super().__init__()
        self.failure = failure
        self.arguments: list[Any] = []

    def __call__(self, args: Any) -> tuple[dict[str, Any], Path]:
        self.arguments.append(args)
        result, run_dir = super().__call__(args)
        trigger_hard = args.suite == "all"
        result["runtime"]["deadline_seconds"] = args.deadline_seconds
        result["config"] = {
            "trigger_case_ids": list(args.trigger_case),
            "behavior_case_ids": list(args.behavior_case),
            "trigger_repeats": args.trigger_repeats,
            "behavior_repeats": args.behavior_repeats,
        }
        dimensions: dict[str, Any] = {
            "correctness": {
                "status": "pass",
                "gates": [
                    {
                        "id": "candidate-non-inferiority",
                        "status": "pass",
                        "hard": True,
                        "observed": 0.0,
                        "required": -0.05,
                    },
                    {
                        "id": "retained-skill-baseline-value",
                        "status": "pass",
                        "hard": True,
                        "observed": 0.1,
                        "required": 0.05,
                    },
                ],
            },
            "safety": {
                "status": "pass",
                "gates": [
                    {
                        "id": "protected-check:development-safety",
                        "status": "pass",
                        "hard": True,
                        "observed": {"candidate_failures": 0},
                        "required": {"candidate_failures": 0},
                    }
                ],
            },
            "triggering": {
                "status": "pass" if trigger_hard else "insufficient-evidence",
                "gates": [
                    {
                        "id": metric + "-non-inferiority",
                        "status": "pass" if trigger_hard else "insufficient-evidence",
                        "hard": trigger_hard,
                        "observed": 0.0 if trigger_hard else None,
                        "required": -0.05,
                    }
                    for metric in ("recall", "specificity")
                ],
            },
            "context": {
                "status": "pass",
                "gates": [
                    {
                        "id": "meaningful-context-reduction",
                        "status": "pass",
                        "hard": True,
                        "observed": {"thresholds_met": ["skill_md_body_characters"]},
                        "required": {"at_least_one_minimum_reduction": True},
                    }
                ],
            },
            "integrity": {
                "status": "insufficient-evidence",
                "gates": [
                    {
                        "id": gate_id,
                        "status": (
                            "insufficient-evidence"
                            if gate_id
                            in {
                                "complete-suite-coverage",
                                "minimum-trigger-repeats",
                                "minimum-behavior-repeats",
                            }
                            else "pass"
                        ),
                        "hard": True,
                        "observed": (
                            {
                                "current_trigger_errors": 0 if trigger_hard else None,
                                "candidate_trigger_errors": 0 if trigger_hard else None,
                                "behavior_failed_runs": {
                                    "skill": 0,
                                    "baseline": 0,
                                    "candidate": 0,
                                },
                            }
                            if gate_id == "execution-completeness"
                            else True
                        ),
                        "required": True,
                    }
                    for gate_id in (
                        "repository-review-policy",
                        "complete-suite-coverage",
                        "minimum-trigger-repeats",
                        "minimum-behavior-repeats",
                        "behavior-evidence-coverage",
                        "execution-completeness",
                        "judgment-completeness",
                        "fixture-fidelity",
                        "fixture-parity",
                        "condition-blind-grading",
                    )
                ],
            },
        }
        if self.failure == "safety":
            gate = dimensions["safety"]["gates"][0]
            gate["status"] = "fail"
            dimensions["safety"]["status"] = "fail"
        elif self.failure == "missing-protected":
            dimensions["safety"]["gates"] = []
            dimensions["safety"]["status"] = "not-applicable"
        elif self.failure == "budget":
            gate = next(
                item
                for item in dimensions["integrity"]["gates"]
                if item["id"] == "execution-completeness"
            )
            gate["status"] = "fail"
            gate["observed"]["behavior_failed_runs"]["candidate"] = 1
        elif self.failure == "controls":
            result["runtime"]["deadline_seconds"] = None
        result["optimisation_review"] = {
            "verdict": "insufficient-evidence",
            "approved": False,
            "hard_failure": self.failure is not None,
            "hard_blocked": True,
            "trigger_gate_scope": {
                "canonical_fields": ["name", "description"],
                "changed": trigger_hard,
                "changed_fields": ["description"] if trigger_hard else [],
                "trigger_gate_mode": "blocking" if trigger_hard else "observational",
            },
            "dimensions": dimensions,
            "no_aggregate_override": True,
        }
        (run_dir / "results.json").write_text(json.dumps(result) + "\n", encoding="utf-8")
        return result, run_dir


class ProfileContractTests(unittest.TestCase):
    def test_loads_required_and_observed_profiles_with_pinned_judge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))

            contract = load_profile_contract(fixture.profiles)

        self.assertEqual(contract.schema_version, 1)
        self.assertEqual([profile.role for profile in contract.profiles], ["required", "observed"])
        self.assertEqual(contract.judge_policy.model, "fake-judge-v1")
        self.assertEqual(len(contract.digest_sha256), 64)

    def test_rejects_runtime_default_with_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            payload = json.loads(fixture.profiles.read_text(encoding="utf-8"))
            payload["profiles"][0]["model"] = "runtime-default"
            fixture.profiles.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "runtime-default"):
                load_profile_contract(fixture.profiles)

    def test_rejects_pinned_identifier_with_surrounding_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            payload = json.loads(fixture.profiles.read_text(encoding="utf-8"))
            payload["judge_policy"]["model"] = " fake-judge-v1"
            fixture.profiles.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "surrounding whitespace"):
                load_profile_contract(fixture.profiles)

    def test_rejects_profile_judge_that_differs_from_pinned_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            payload = json.loads(fixture.profiles.read_text(encoding="utf-8"))
            payload["profiles"][1]["judge_model"] = "other-judge"
            fixture.profiles.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "must match pinned judge_policy.model"):
                load_profile_contract(fixture.profiles)

    def test_required_profiles_always_run_and_observed_are_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            contract = load_profile_contract(fixture.profiles)

            required_only = select_profiles(contract, [], include_all_observed=False)
            both = select_profiles(
                contract,
                ["fake-observed"],
                include_all_observed=False,
            )

        self.assertEqual([profile.id for profile in required_only], ["fake-required"])
        self.assertEqual(
            [profile.id for profile in both],
            ["fake-required", "fake-observed"],
        )


class CaseGroupAndUniverseTests(unittest.TestCase):
    def test_case_groups_form_complete_development_and_held_back_partition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            spec = load_eval_spec(fixture.skill, fixture.repo / "evals")

            groups = load_case_groups(fixture.case_groups, spec)

        self.assertEqual([group.kind for group in groups], ["development", "held-back"])
        self.assertEqual(groups[1].id, "held-back-v1")

    def test_case_groups_reject_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            payload = json.loads(fixture.case_groups.read_text(encoding="utf-8"))
            payload["groups"][1]["trigger_cases"] = [1, 2]
            fixture.case_groups.write_text(json.dumps(payload), encoding="utf-8")
            spec = load_eval_spec(fixture.skill, fixture.repo / "evals")

            with self.assertRaisesRegex(EvalError, "overlaps an earlier group"):
                load_case_groups(fixture.case_groups, spec)

    def test_single_universe_requires_documented_limitation(self) -> None:
        with self.assertRaisesRegex(EvalError, "requires --universe-limitation"):
            validate_universes(["repository"], None)

        self.assertEqual(
            validate_universes(
                ["repository"],
                "This review measures normal deployment only.",
            ),
            ("repository",),
        )
        self.assertEqual(validate_universes([], None), ("repository", "isolated"))
        with self.assertRaisesRegex(EvalError, "only valid when selecting one"):
            validate_universes(
                ["repository", "isolated"],
                "No limitation applies.",
            )


class CapabilityReviewOrchestrationTests(unittest.TestCase):
    def test_observed_failure_is_visible_but_does_not_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            fake = FakeEvaluationRunner()

            review, local_root = run_capability_review(config, fake)

            self.assertEqual(review["aggregate"]["verdict"], "approved")
            self.assertEqual(review["aggregate"]["required_blockers"], [])
            self.assertEqual(review["aggregate"]["observed_failures"], ["fake-observed"])
            self.assertFalse(review["aggregate"]["observed_profiles_block"])
            coverage_detail = review["aggregate"]["coverage_gate"]["detail"]
            self.assertIn("declarative", coverage_detail)
            self.assertIn("process controls", coverage_detail)
            self.assertIn("whole-suite", coverage_detail)
            self.assertEqual(len(fake.calls), 4)
            self.assertEqual(
                {call[2] for call in fake.calls},
                {"repository", "isolated"},
            )
            local_manifest = json.loads((local_root / "review.json").read_text(encoding="utf-8"))
            self.assertEqual(local_manifest["status"], "completed")
            self.assertEqual(len(local_manifest["cells"]), 4)

    def test_required_profile_failure_blocks_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config(include_observed=False)
            fake = FakeEvaluationRunner(required_verdict="rejected")

            review, _local_root = run_capability_review(config, fake)

        self.assertEqual(review["aggregate"]["verdict"], "rejected")
        self.assertEqual(review["aggregate"]["required_blockers"], ["fake-required"])

    def test_default_case_group_keeps_evidence_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config(include_observed=False)
            spec = load_eval_spec(fixture.skill, fixture.repo / "evals")
            config = replace(
                config,
                case_group_source=None,
                case_groups=load_case_groups(None, spec),
            )

            review, _local_root = run_capability_review(config, FakeEvaluationRunner())

        self.assertEqual(review["aggregate"]["verdict"], "insufficient-evidence")
        self.assertEqual(
            review["aggregate"]["coverage_gate"]["status"],
            "insufficient-evidence",
        )

    def test_single_repeat_keeps_evidence_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = replace(
                fixture.config(include_observed=False),
                trigger_repeats=1,
                behavior_repeats=1,
            )

            review, _local_root = run_capability_review(config, FakeEvaluationRunner())

        self.assertEqual(review["aggregate"]["verdict"], "insufficient-evidence")
        self.assertFalse(review["aggregate"]["coverage_gate"]["repeated"])

    def test_eval_fixture_drift_between_cells_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config(include_observed=False)
            fake = FakeEvaluationRunner()

            def drifting_runner(args: Any) -> tuple[dict[str, Any], Path]:
                result = fake(args)
                if len(fake.calls) == 1:
                    fixture_file = fixture.eval_path.parent / "fixtures" / "input.txt"
                    fixture_file.parent.mkdir()
                    fixture_file.write_text("changed fixture\n", encoding="utf-8")
                return result

            with self.assertRaisesRegex(EvalError, "evaluation bundle changed"):
                run_capability_review(config, drifting_runner)

            manifests = list(fixture.output.rglob("review.json"))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")


class RoutineScreenTests(unittest.TestCase):
    def test_changed_discovery_runs_compact_triggers_and_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            runner = RoutineEvaluationRunner()

            review, local_root = run_routine_screen(fixture.routine_config(), runner)
            manifest = json.loads((local_root / "review.json").read_text(encoding="utf-8"))

        self.assertEqual(review["aggregate"]["outcome"], "eligible-for-escalation")
        self.assertFalse(review["aggregate"]["approval_possible"])
        self.assertEqual(review["coverage"]["trigger_policy"], "blocking-compact")
        self.assertFalse(review["coverage"]["held_back_cases_used"])
        self.assertEqual(len(runner.arguments), 2)
        self.assertEqual(
            {tuple(args.trigger_case) for args in runner.arguments},
            {("1", "3")},
        )
        self.assertEqual(
            {tuple(args.behavior_case) for args in runner.arguments},
            {("1", "3")},
        )
        self.assertTrue(all(args.deadline_seconds == 3300 for args in runner.arguments))
        self.assertEqual(manifest["aggregate"]["outcome"], "eligible-for-escalation")

    def test_unchanged_discovery_omits_observational_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            (fixture.candidate / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Current demo\n---\n# Smaller candidate\n",
                encoding="utf-8",
            )
            runner = RoutineEvaluationRunner()

            review, _local_root = run_routine_screen(fixture.routine_config(), runner)

        self.assertEqual(review["aggregate"]["outcome"], "eligible-for-escalation")
        self.assertEqual(review["coverage"]["trigger_policy"], "observational-omitted")
        self.assertTrue(all(args.suite == "behavior" for args in runner.arguments))
        self.assertTrue(all(args.trigger_case == [] for args in runner.arguments))

    def test_safety_failure_rejects_but_budget_failure_is_incomplete(self) -> None:
        for failure, expected in (
            ("safety", "reject"),
            ("budget", "incomplete"),
            ("missing-protected", "incomplete"),
        ):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp_dir:
                fixture = CapabilityReviewFixture(Path(temp_dir))
                review, _local_root = run_routine_screen(
                    fixture.routine_config(),
                    RoutineEvaluationRunner(failure=failure),
                )
                self.assertEqual(review["aggregate"]["outcome"], expected)

    def test_full_escalation_requires_matching_eligible_pins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            _review, local_root = run_routine_screen(
                fixture.routine_config(),
                RoutineEvaluationRunner(),
            )
            full_config = fixture.config(include_observed=False)

            validate_routine_escalation(local_root / "review.json", full_config)
            harness = fixture.repo / "harnesses" / "codex.json"
            original_harness = harness.read_text(encoding="utf-8")
            harness.write_text(
                '{"project_install_root": ".changed", "user_install_root": "~/.changed"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "harness_manifest_digest_sha256"):
                validate_routine_escalation(local_root / "review.json", full_config)
            harness.write_text(original_harness, encoding="utf-8")
            (fixture.candidate / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Candidate demo\n---\n# Drifted\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "candidate_digest_sha256"):
                validate_routine_escalation(local_root / "review.json", full_config)

    def test_contract_rejects_held_back_cases_and_invalid_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            valid_contract = fixture.routine_config().contract
            fixture.routine_contract.write_text(
                '{"schema_version":1,"trigger_cases":[1,2],"behavior_cases":[1,2]}\n',
                encoding="utf-8",
            )
            review = fixture.config(include_observed=False)
            spec = load_eval_spec(fixture.skill, fixture.repo / "evals")
            with self.assertRaisesRegex(EvalError, "held-back cases are reserved"):
                load_routine_screen_contract(
                    fixture.routine_contract,
                    spec,
                    review.case_groups,
                )
            with self.assertRaisesRegex(EvalError, "may not exceed"):
                RoutineScreenConfig(
                    review=replace(
                        review,
                        trigger_repeats=1,
                        behavior_repeats=1,
                        jobs=2,
                    ),
                    contract_source=fixture.routine_contract,
                    contract=valid_contract,
                    budget_seconds=3601,
                )
            with self.assertRaisesRegex(EvalError, "at least one required profile"):
                RoutineScreenConfig(
                    review=replace(
                        review,
                        profiles=(),
                        trigger_repeats=1,
                        behavior_repeats=1,
                        jobs=2,
                    ),
                    contract_source=fixture.routine_contract,
                    contract=valid_contract,
                )

    def test_routine_rejects_runner_control_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            with self.assertRaisesRegex(EvalError, "changed pinned deadline"):
                run_routine_screen(
                    fixture.routine_config(),
                    RoutineEvaluationRunner(failure="controls"),
                )
            manifests = list(fixture.output.rglob("review.json"))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")


class DurableExportTests(unittest.TestCase):
    def test_summary_is_deterministic_bounded_and_omits_raw_evidence_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())

            first = build_durable_summary(
                review,
                config,
                disposition="retain",
                reviewer="Test Reviewer",
                rationale="Required profiles pass; the observed failure remains visible.",
            )
            second = build_durable_summary(
                review,
                config,
                disposition="retain",
                reviewer="Test Reviewer",
                rationale="Required profiles pass; the observed failure remains visible.",
            )
            first_json, first_markdown = export_durable_summary(
                first,
                repo_root=fixture.repo,
            )
            json_bytes = first_json.read_bytes()
            markdown_bytes = first_markdown.read_bytes()
            second_json, second_markdown = export_durable_summary(
                second,
                repo_root=fixture.repo,
            )

            self.assertEqual(first, second)
            self.assertEqual(json_bytes, second_json.read_bytes())
            self.assertEqual(markdown_bytes, second_markdown.read_bytes())
            exported = json_bytes.decode()
            markdown = markdown_bytes.decode()
            for artifact in (exported, markdown):
                self.assertNotIn(str(fixture.repo), artifact)
                self.assertNotIn(str(fixture.candidate), artifact)
                self.assertNotIn("RAW PROMPT MUST NOT EXPORT", artifact)
                self.assertNotIn("RAW COMMAND OUTPUT MUST NOT EXPORT", artifact)
                self.assertNotIn("DEVELOPMENT PROMPT MUST NOT EXPORT", artifact)
            self.assertLess(len(json_bytes), 256_000)
            self.assertFalse(first["human_review"]["automatic_promotion"])
            self.assertIn("${CANDIDATE_DIR}", first["reproduction"]["argv"])
            self.assertTrue(
                any(
                    "declarative process controls" in limitation
                    and "held-back-only non-inferiority" in limitation
                    for limitation in first["confidence_limitations"]
                )
            )
            self.assertIn("## Baseline, Current, and Candidate metrics", markdown)
            self.assertIn("## Context footprint", markdown)
            self.assertIn("## Gate results", markdown)

    def test_export_refuses_different_payload_for_existing_review_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())
            first = build_durable_summary(
                review,
                config,
                disposition="retain",
                reviewer="First Reviewer",
                rationale="Keep the current capability.",
            )
            different = build_durable_summary(
                review,
                config,
                disposition="compress",
                reviewer="Second Reviewer",
                rationale="Compress the current capability.",
            )

            json_path, markdown_path = export_durable_summary(first, repo_root=fixture.repo)
            json_bytes = json_path.read_bytes()
            markdown_bytes = markdown_path.read_bytes()
            export_durable_summary(first, repo_root=fixture.repo)
            with self.assertRaisesRegex(EvalError, first["review_id"]):
                export_durable_summary(different, repo_root=fixture.repo)

            self.assertEqual(json_path.read_bytes(), json_bytes)
            self.assertEqual(markdown_path.read_bytes(), markdown_bytes)

    def test_export_refuses_incomplete_existing_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())
            summary = build_durable_summary(
                review,
                config,
                disposition="retain",
                reviewer="Test Reviewer",
                rationale="Keep the current capability.",
            )

            json_path, markdown_path = export_durable_summary(summary, repo_root=fixture.repo)
            markdown_path.unlink()

            with self.assertRaisesRegex(EvalError, "incomplete"):
                export_durable_summary(summary, repo_root=fixture.repo)

            self.assertTrue(json_path.is_file())
            self.assertFalse(markdown_path.exists())

    def test_summary_rejects_absolute_path_in_human_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())

            for rationale in (
                "See /tmp/private-review-notes before deciding.",
                "See `/home/reviewer/private-notes` before deciding.",
                'See "C:\\Users\\reviewer\\notes.txt" before deciding.',
                "See \\\\server\\share\\private-review-notes before deciding.",
                "See \\\\?\\C:\\private-review-notes before deciding.",
                "See \\\\.\\PhysicalDrive0 before deciding.",
                "See C:/private-review-notes before deciding.",
                "See //server/share/private-review-notes before deciding.",
                "See file://server/share/private-review-notes before deciding.",
                "See file:///C:/private-review-notes before deciding.",
            ):
                with self.subTest(rationale=rationale):
                    with self.assertRaisesRegex(EvalError, "absolute path"):
                        build_durable_summary(
                            review,
                            config,
                            disposition="retain",
                            reviewer="Test Reviewer",
                            rationale=rationale,
                        )

    def test_summary_allows_https_url_in_human_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())

            summary = build_durable_summary(
                review,
                config,
                disposition="retain",
                reviewer="Test Reviewer",
                rationale="See https://example.com/review-notes before deciding.",
            )

        self.assertEqual(
            summary["human_review"]["rationale"],
            "See https://example.com/review-notes before deciding.",
        )

    def test_export_rejects_unc_and_device_paths_before_writing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())
            summary = build_durable_summary(
                review,
                config,
                disposition="retain",
                reviewer="Test Reviewer",
                rationale="Keep the current capability.",
            )

            for index, rationale in enumerate(
                (
                    "See \\\\server\\share\\private-review-notes before deciding.",
                    "See \\\\?\\C:\\private-review-notes before deciding.",
                    "See \\\\.\\PhysicalDrive0 before deciding.",
                    "See C:/private-review-notes before deciding.",
                    "See //server/share/private-review-notes before deciding.",
                    "See file://server/share/private-review-notes before deciding.",
                    "See file:///C:/private-review-notes before deciding.",
                )
            ):
                with self.subTest(rationale=rationale):
                    tampered = json.loads(json.dumps(summary))
                    tampered["review_id"] = f"tampered-{index}"
                    tampered["human_review"]["rationale"] = rationale

                    with self.assertRaisesRegex(EvalError, "absolute path"):
                        export_durable_summary(tampered, repo_root=fixture.repo)

            review_dir = fixture.repo / "evals" / "demo" / "reviews"
            self.assertFalse(review_dir.exists())

    def test_export_args_fail_before_matrix_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            base_argv = [
                "--repo-root",
                str(fixture.repo),
                "--skill",
                "demo",
                "--candidate",
                str(fixture.candidate),
                "--profiles",
                str(fixture.profiles),
                "--case-groups",
                str(fixture.case_groups),
                "--export",
                "--disposition",
                "retain",
            ]

            for human_args in (
                [
                    "--reviewer",
                    "   ",
                    "--disposition-rationale",
                    "Keep the capability.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See /tmp/private-review-notes.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See \\\\server\\share\\private-review-notes.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See \\\\?\\C:\\private-review-notes.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See C:/private-review-notes.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See //server/share/private-review-notes.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See file://server/share/private-review-notes.",
                ],
                [
                    "--reviewer",
                    "Test Reviewer",
                    "--disposition-rationale",
                    "See file:///C:/private-review-notes.",
                ],
            ):
                with self.subTest(human_args=human_args):
                    fake = FakeEvaluationRunner()
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        exit_code = review_skill_capability.main(
                            base_argv + human_args,
                            evaluation_runner=fake,
                        )

                    self.assertEqual(exit_code, 1)
                    if human_args[1].strip():
                        self.assertIn("absolute path", stderr.getvalue())
                    self.assertEqual(fake.calls, [])

    def test_plan_validates_numeric_controls_before_matrix_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            base_argv = [
                "--repo-root",
                str(fixture.repo),
                "--skill",
                "demo",
                "--candidate",
                str(fixture.candidate),
                "--profiles",
                str(fixture.profiles),
                "--case-groups",
                str(fixture.case_groups),
                "--plan",
            ]
            fake = FakeEvaluationRunner()
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                invalid_exit = review_skill_capability.main(
                    base_argv + ["--trigger-repeats", "0"],
                    evaluation_runner=fake,
                )
            with contextlib.redirect_stdout(io.StringIO()):
                valid_exit = review_skill_capability.main(
                    base_argv,
                    evaluation_runner=fake,
                )

            self.assertEqual(invalid_exit, 1)
            self.assertIn("--trigger-repeats must be greater than zero", stderr.getvalue())
            self.assertEqual(valid_exit, 0)
            self.assertEqual(fake.calls, [])

    def test_cli_end_to_end_uses_fake_profiles_without_external_services(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            fake = FakeEvaluationRunner()
            stdout = io.StringIO()
            stderr = io.StringIO()
            argv = [
                "--repo-root",
                str(fixture.repo),
                "--skill",
                "demo",
                "--candidate",
                str(fixture.candidate),
                "--profiles",
                str(fixture.profiles),
                "--observed-profile",
                "fake-observed",
                "--case-groups",
                str(fixture.case_groups),
                "--output-root",
                str(fixture.output),
                "--reviewer",
                "Fake Reviewer",
                "--disposition",
                "retain",
                "--disposition-rationale",
                "Fake deterministic review.",
                "--export",
            ]

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = review_skill_capability.main(
                    argv,
                    evaluation_runner=fake,
                )

            self.assertEqual(exit_code, 0, stderr.getvalue())
            self.assertIn("Evidence verdict: approved", stdout.getvalue())
            exports = list((fixture.repo / "evals" / "demo" / "reviews").glob("*.json"))
            self.assertEqual(len(exports), 1)
            payload = json.loads(exports[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["aggregate"]["observed_failures"], ["fake-observed"])
            self.assertEqual(len(fake.calls), 4)

    def test_routine_cli_rejects_export_observed_profiles_and_unpaired_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            base = [
                "--repo-root",
                str(fixture.repo),
                "--skill",
                "demo",
                "--candidate",
                str(fixture.candidate),
                "--profiles",
                str(fixture.profiles),
                "--case-groups",
                str(fixture.case_groups),
            ]
            for extra, message in (
                (
                    ["--workflow", "routine", "--observed-profile", "fake-observed"],
                    "required profiles only",
                ),
                (
                    [
                        "--workflow",
                        "routine",
                        "--export",
                        "--reviewer",
                        "Reviewer",
                        "--disposition",
                        "retain",
                        "--disposition-rationale",
                        "No promotion.",
                    ],
                    "report-only",
                ),
                (["--human-opt-in"], "requires --escalate-from"),
                (
                    ["--budget-seconds", "1200"],
                    "require --workflow routine",
                ),
            ):
                with self.subTest(extra=extra):
                    stderr = io.StringIO()
                    fake = RoutineEvaluationRunner()
                    with contextlib.redirect_stderr(stderr):
                        exit_code = review_skill_capability.main(
                            base + extra,
                            evaluation_runner=fake,
                        )
                    self.assertEqual(exit_code, 1)
                    self.assertIn(message, stderr.getvalue())
                    self.assertEqual(fake.calls, [])

    def test_routine_cli_reports_eligibility_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            fake = RoutineEvaluationRunner()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = review_skill_capability.main(
                    [
                        "--repo-root",
                        str(fixture.repo),
                        "--skill",
                        "demo",
                        "--candidate",
                        str(fixture.candidate),
                        "--profiles",
                        str(fixture.profiles),
                        "--case-groups",
                        str(fixture.case_groups),
                        "--routine-contract",
                        str(fixture.routine_contract),
                        "--workflow",
                        "routine",
                        "--output-root",
                        str(fixture.output),
                    ],
                    evaluation_runner=fake,
                )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Routine outcome: eligible-for-escalation", output)
            self.assertNotIn("approved", output.lower())


if __name__ == "__main__":
    unittest.main()
