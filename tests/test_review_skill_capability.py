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
    build_durable_summary,
    export_durable_summary,
    load_case_groups,
    load_profile_contract,
    run_capability_review,
    select_profiles,
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
                            "trigger_cases": [1],
                            "behavior_cases": [1],
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
            self.assertIn("## Baseline, Current, and Candidate metrics", markdown)
            self.assertIn("## Context footprint", markdown)
            self.assertIn("## Gate results", markdown)

    def test_summary_rejects_absolute_path_in_human_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = CapabilityReviewFixture(Path(temp_dir))
            config = fixture.config()
            review, _local_root = run_capability_review(config, FakeEvaluationRunner())

            for rationale in (
                "See /tmp/private-review-notes before deciding.",
                "See `/home/reviewer/private-notes` before deciding.",
                'See "C:\\Users\\reviewer\\notes.txt" before deciding.',
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


if __name__ == "__main__":
    unittest.main()
