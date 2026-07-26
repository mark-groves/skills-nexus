import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "scripts"))

import ablate_skill_components  # noqa: E402
import validate_repo  # noqa: E402
from skill_eval.core import EvalError  # noqa: E402
from skill_review.ablation import (  # noqa: E402
    ComponentAblationConfig,
    create_component_candidate,
    load_component_contract,
    run_component_ablation,
)
from skill_review.core import (  # noqa: E402
    CapabilityReviewConfig,
    CaseGroup,
    JudgePolicy,
    ModelProfile,
    ProfileContract,
    _case_groups_digest,
    canonical_digest,
)


class AblationFixture:
    def __init__(self, root: Path) -> None:
        self.repo = root / "repo"
        self.skill = self.repo / "skills" / "demo"
        self.eval_dir = self.repo / "evals" / "demo"
        self.skill.mkdir(parents=True)
        self.eval_dir.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text(
            """\
---
name: demo
description: Demonstrate component ablation
---
# Demo

## Alpha

Alpha has the larger removable body.
It deliberately saves more bytes than Beta.

## Beta

Beta is individually removable.

## Safety

Never remove this protected safety section.
""",
            encoding="utf-8",
        )
        self.components = self.eval_dir / "components.json"
        self.components.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "components": [
                        {
                            "id": "alpha",
                            "source": "SKILL.md",
                            "heading": "## Alpha",
                            "class": "workflow",
                            "protected": False,
                        },
                        {
                            "id": "beta",
                            "source": "SKILL.md",
                            "heading": "## Beta",
                            "class": "workflow",
                            "protected": False,
                        },
                        {
                            "id": "safety",
                            "source": "SKILL.md",
                            "heading": "## Safety",
                            "class": "safety",
                            "protected": True,
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.eval_dir / "evals.json").write_text(
            json.dumps(
                {
                    "skill_name": "demo",
                    "trigger_evals": [{"id": 1, "query": "demo", "should_trigger": True}],
                    "behavior_evals": [
                        {
                            "id": 1,
                            "prompt": "demo",
                            "expected_behavior": "demo",
                            "fixtures": [],
                            "checks": ["demo"],
                        }
                    ],
                    "review_policy": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        judge = JudgePolicy(
            id="judge-v1",
            model="fake-judge-v1",
            protocol="skill-eval-candidate-v3-condition-blind",
        )
        profile = ModelProfile(
            id="required-v1",
            adapter="codex",
            model="fake-task-v1",
            judge_model="fake-judge-v1",
            required=True,
        )
        contract_payload = {
            "schema_version": 1,
            "judge_policy": judge.as_dict(),
            "profiles": [profile.as_dict()],
        }
        profile_contract = ProfileContract(
            schema_version=1,
            judge_policy=judge,
            profiles=(profile,),
            digest_sha256=canonical_digest(contract_payload),
        )
        (self.repo / "eval-profiles.json").write_text(
            json.dumps(contract_payload) + "\n",
            encoding="utf-8",
        )
        review = CapabilityReviewConfig(
            repo_root=self.repo,
            skill="demo",
            candidate=root / "pending",
            profile_source=self.repo / "eval-profiles.json",
            contract=profile_contract,
            profiles=(profile,),
            case_group_source=None,
            case_groups=(
                CaseGroup("development", "development", ("1",), ("1",)),
                CaseGroup("held-back-v1", "held-back", ("2",), ("2",)),
            ),
            universes=("repository", "isolated"),
            universe_limitation=None,
            trigger_repeats=2,
            behavior_repeats=2,
            activation_threshold=0.5,
            jobs=1,
            timeout=10,
            codex_binary="fake-codex",
            sandbox="workspace-write",
            allow_fixture_scripts=False,
            output_root=root / "local-evidence",
        )
        self.config = ComponentAblationConfig(
            review=review,
            components_source=self.components,
            output_root=root / "local-evidence",
        )


class MatrixRunner:
    def __init__(self, outcomes: dict[frozenset[str], str]) -> None:
        self.outcomes = outcomes
        self.calls: list[frozenset[str]] = []
        self.candidates: list[str] = []

    def __call__(self, config: CapabilityReviewConfig) -> tuple[dict[str, Any], Path]:
        text = (config.candidate / "SKILL.md").read_text(encoding="utf-8")
        self.candidates.append(text)
        removed = frozenset(
            component
            for component, heading in (
                ("alpha", "## Alpha"),
                ("beta", "## Beta"),
                ("safety", "## Safety"),
            )
            if heading not in text
        )
        self.calls.append(removed)
        verdict = self.outcomes.get(removed, "approved")
        status = "pass" if verdict == "approved" else "fail"
        delta = 0.0 if verdict == "approved" else -0.25
        cells = []
        for universe in config.universes:
            cells.append(
                {
                    "profile_id": "required-v1",
                    "profile_role": "required",
                    "universe": universe,
                    "verdict": verdict,
                    "metrics": {
                        "candidate_comparison": {
                            "candidate_minus_current_quality": delta,
                            "paired_checks": {
                                "wins": 0,
                                "regressions": 0 if verdict == "approved" else 1,
                                "ties": 4,
                                "unknown": 0,
                            },
                        }
                    },
                    "gates": {
                        "verdict": verdict,
                        "dimensions": {
                            "correctness": {
                                "status": status,
                                "gates": [
                                    {
                                        "id": "required-check",
                                        "status": status,
                                        "hard": True,
                                        "observed": 1 if verdict == "approved" else 0,
                                        "required": 1,
                                    }
                                ],
                            }
                        },
                    },
                }
            )
        return (
            {
                "cells": cells,
                "aggregate": {
                    "verdict": verdict,
                    "required_blockers": ([] if verdict == "approved" else ["required-v1"]),
                    "observed_failures": [],
                    "no_aggregate_override": True,
                },
            },
            config.output_root,
        )


class ComponentSelectorTests(unittest.TestCase):
    def test_heading_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            payload = json.loads(fixture.components.read_text(encoding="utf-8"))
            payload["components"][0]["heading"] = "## Alpha changed"
            fixture.components.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "found 0"):
                load_component_contract(fixture.components, fixture.skill)

    def test_ambiguous_heading_and_escape_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            skill_md = fixture.skill / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8") + "\n## Alpha\n\nDuplicate.\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(EvalError, "found 2"):
                load_component_contract(fixture.components, fixture.skill)

            payload = json.loads(fixture.components.read_text(encoding="utf-8"))
            payload["components"][0]["source"] = "../outside.md"
            fixture.components.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(EvalError, "stay within"):
                load_component_contract(fixture.components, fixture.skill)

    def test_adjacent_section_removal_preserves_neighbor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            contract = load_component_contract(fixture.components, fixture.skill)
            candidate = Path(temp_dir) / "candidate"

            create_component_candidate(
                fixture.skill,
                candidate,
                contract,
                {"alpha"},
            )

            text = (candidate / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("## Alpha", text)
            self.assertNotIn("larger removable body", text)
            self.assertIn("## Beta", text)
            self.assertIn("Beta is individually removable.", text)
            self.assertIn("## Safety", text)

    def test_h1_heading_terminates_prior_component_span(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            (fixture.skill / "SKILL.md").write_text(
                """\
---
name: demo
description: Demonstrate component ablation
---
# Demo

## Alpha

Alpha body.

# Critical chapter

MUST KEEP THIS UNDECLARED CHAPTER.

## Beta

Beta body.

## Safety

Protected.
""",
                encoding="utf-8",
            )
            contract = load_component_contract(fixture.components, fixture.skill)
            self.assertNotIn("Critical chapter", contract.spans["alpha"].text)

            candidate = Path(temp_dir) / "candidate"
            create_component_candidate(fixture.skill, candidate, contract, {"alpha"})
            text = (candidate / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("## Alpha", text)
            self.assertIn("Critical chapter", text)
            self.assertIn("MUST KEEP THIS UNDECLARED CHAPTER.", text)
            self.assertIn("## Beta", text)

    def test_commonmark_atx_boundaries_terminate_prior_component_span(self) -> None:
        boundaries = (
            " # Indented H1",
            "  # Indented H1",
            "   # Indented H1",
            "  ## Indented H2",
            "#",
            "##",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temp_dir:
                fixture = AblationFixture(Path(temp_dir))
                (fixture.skill / "SKILL.md").write_text(
                    f"""\
---
name: demo
description: Demonstrate component ablation
---
# Demo

## Alpha

Alpha body.

{boundary}

MUST KEEP THIS UNDECLARED SECTION.

## Beta

Beta body.

## Safety

Protected.
""",
                    encoding="utf-8",
                )
                contract = load_component_contract(fixture.components, fixture.skill)
                self.assertNotIn(
                    "MUST KEEP THIS UNDECLARED SECTION.",
                    contract.spans["alpha"].text,
                )

                candidate = Path(temp_dir) / "candidate"
                create_component_candidate(fixture.skill, candidate, contract, {"alpha"})
                text = (candidate / "SKILL.md").read_text(encoding="utf-8")
                self.assertNotIn("## Alpha", text)
                self.assertIn(boundary, text)
                self.assertIn("MUST KEEP THIS UNDECLARED SECTION.", text)
                self.assertIn("## Beta", text)

    def test_setext_heading_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            (fixture.skill / "SKILL.md").write_text(
                """\
---
name: demo
description: Demonstrate component ablation
---
# Demo

## Alpha

Alpha body.

Setext Section
--------------

Undeclared setext body.

## Beta

Beta body.

## Safety

Protected.
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "setext"):
                load_component_contract(fixture.components, fixture.skill)

    def test_candidate_removal_preserves_source_newlines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            source = (
                b"---\r\n"
                b"name: demo\r\n"
                b"description: Demonstrate component ablation\r\n"
                b"---\r\n"
                b"# Demo\r\n"
                b"\r\n"
                b"## Alpha\r\n"
                b"\r\n"
                b"Alpha has the larger removable body.\r\n"
                b"It deliberately saves more bytes than Beta.\r\n"
                b"\r\n"
                b"## Beta\r\n"
                b"\r\n"
                b"Beta is individually removable.\r\n"
                b"\r\n"
                b"## Safety\r\n"
                b"\r\n"
                b"Never remove this protected safety section.\r\n"
            )
            (fixture.skill / "SKILL.md").write_bytes(source)
            contract = load_component_contract(fixture.components, fixture.skill)
            candidate = Path(temp_dir) / "candidate"
            create_component_candidate(fixture.skill, candidate, contract, {"alpha"})
            cand = (candidate / "SKILL.md").read_bytes()
            removed = contract.spans["alpha"].text.encode("utf-8")
            self.assertIn(b"## Beta\r\n", cand)
            self.assertIn(b"## Safety\r\n", cand)
            self.assertNotIn(b"## Alpha\r\n", cand)
            self.assertEqual(cand.count(b"\r"), source.count(b"\r") - removed.count(b"\r"))
            self.assertEqual(len(cand), len(source) - len(removed))

    def test_symlinked_component_source_is_rejected_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            (fixture.skill / "linked.md").symlink_to(fixture.skill / "SKILL.md")
            payload = json.loads(fixture.components.read_text(encoding="utf-8"))
            payload["components"] = [
                {
                    "id": "linked",
                    "source": "linked.md",
                    "heading": "## Alpha",
                    "class": "workflow",
                    "protected": False,
                }
            ]
            fixture.components.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "must not traverse a runtime symlink"):
                load_component_contract(fixture.components, fixture.skill)

    def test_heading_inside_fenced_code_is_not_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            skill_md = fixture.skill / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8")
                + "\n```markdown\n## Phantom\n\nNot a section.\n```\n",
                encoding="utf-8",
            )
            payload = json.loads(fixture.components.read_text(encoding="utf-8"))
            payload["components"] = [
                {
                    "id": "phantom",
                    "source": "SKILL.md",
                    "heading": "## Phantom",
                    "class": "workflow",
                    "protected": False,
                }
            ]
            fixture.components.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "found 0"):
                load_component_contract(fixture.components, fixture.skill)

    def test_runtime_excluded_component_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            working = fixture.skill / "working"
            working.mkdir()
            (working / "notes.md").write_text(
                "## Internal\n\nRepository-only notes.\n",
                encoding="utf-8",
            )
            payload = json.loads(fixture.components.read_text(encoding="utf-8"))
            payload["components"] = [
                {
                    "id": "internal",
                    "source": "working/notes.md",
                    "heading": "## Internal",
                    "class": "workflow",
                    "protected": False,
                }
            ]
            fixture.components.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(EvalError, "runtime-excluded"):
                load_component_contract(fixture.components, fixture.skill)

    def test_cli_defaults_follow_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            args = ablate_skill_components.build_parser().parse_args(
                [
                    "--skill",
                    "demo",
                    "--repo-root",
                    str(fixture.repo),
                    "--plan",
                ]
            )

            config, _contract = ablate_skill_components._configuration(args)

            self.assertEqual(
                config.review.profile_source,
                fixture.repo / "eval-profiles.json",
            )
            self.assertEqual(config.output_root, fixture.repo / ".skill-evals")

    def test_cli_plan_rejects_external_component_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            external = Path(temp_dir) / "external-components.json"
            external.write_bytes(fixture.components.read_bytes())
            args = ablate_skill_components.build_parser().parse_args(
                [
                    "--skill",
                    "demo",
                    "--repo-root",
                    str(fixture.repo),
                    "--components",
                    str(external),
                    "--plan",
                ]
            )

            with self.assertRaisesRegex(EvalError, "repository eval directory"):
                ablate_skill_components._configuration(args)

    def test_repo_validator_rejects_dangling_component_metadata_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            fixture.components.unlink()
            fixture.components.symlink_to("missing-components.json")

            with (
                mock.patch.object(
                    validate_repo,
                    "load_component_contract",
                    side_effect=EvalError("dangling metadata rejected"),
                ) as loader,
                mock.patch.object(validate_repo, "REPO_DIR", fixture.repo),
            ):
                validate_repo.ERRORS.clear()
                self.addCleanup(validate_repo.ERRORS.clear)
                validate_repo.validate_evals(fixture.skill, fixture.eval_dir)

            loader.assert_called_once_with(fixture.components, fixture.skill)
            self.assertIn("dangling metadata rejected", validate_repo.ERRORS)


class BackwardEliminationTests(unittest.TestCase):
    def test_repository_local_output_must_stay_under_ignored_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            unsafe = replace(
                fixture.config,
                output_root=fixture.eval_dir / "generated",
            )

            with self.assertRaisesRegex(EvalError, "ignored .skill-evals"):
                run_component_ablation(unsafe, MatrixRunner({}))

            self.assertFalse((fixture.eval_dir / "generated").exists())

    def test_nested_repository_metadata_rechecks_the_complete_eval_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            nested = fixture.eval_dir / "metadata" / "components.json"
            nested.parent.mkdir()
            nested.write_bytes(fixture.components.read_bytes())
            config = replace(fixture.config, components_source=nested)

            record, _local_root = run_component_ablation(config, MatrixRunner({}))

            self.assertEqual(record["status"], "completed")

    def test_protected_components_are_surfaced_and_never_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            runner = MatrixRunner({})

            record, _local_root = run_component_ablation(fixture.config, runner)

            safety = next(item for item in record["components"] if item["id"] == "safety")
            self.assertEqual(safety["status"], "skipped-protected")
            self.assertTrue(all("## Safety" in text for text in runner.candidates))
            self.assertTrue(all("safety" not in removed for removed in runner.calls))

    def test_case_group_digest_matches_capability_review_canonical_form(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            record, _local_root = run_component_ablation(fixture.config, MatrixRunner({}))
            expected = _case_groups_digest(fixture.config.review.case_groups)
            self.assertEqual(record["inputs"]["case_groups_digest_sha256"], expected)

    def test_systemic_eval_error_fails_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))

            def boom(_config: CapabilityReviewConfig) -> tuple[dict[str, Any], Path]:
                raise EvalError("evaluation bundle changed during capability review")

            with self.assertRaisesRegex(EvalError, "evaluation bundle changed"):
                run_component_ablation(fixture.config, boom)

            records = list(fixture.config.output_root.rglob("decision.json"))
            self.assertEqual(len(records), 1)
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "failed")
            self.assertNotEqual(record.get("outcome"), "propose-reduction")
            self.assertFalse(
                any(
                    trial.get("decision") == "invalid-candidate"
                    for round_entry in record.get("rounds", [])
                    for trial in round_entry.get("trials", [])
                )
            )

    def test_individually_safe_but_jointly_unsafe_removals_stop_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))
            runner = MatrixRunner(
                {
                    frozenset({"alpha"}): "approved",
                    frozenset({"beta"}): "approved",
                    frozenset({"alpha", "beta"}): "rejected",
                }
            )

            record, _local_root = run_component_ablation(fixture.config, runner)

            self.assertEqual(
                {runner.calls[0], runner.calls[1]},
                {frozenset({"alpha"}), frozenset({"beta"})},
            )
            self.assertEqual(record["accepted_steps"][0]["component_id"], "alpha")
            self.assertEqual(record["rounds"][1]["status"], "no-safe-removal")
            joint = record["rounds"][1]["trials"][0]
            self.assertEqual(joint["decision"], "rejected")
            self.assertTrue(joint["hard_regressions"])
            self.assertEqual(runner.calls[-1], frozenset({"alpha"}))
            self.assertTrue(record["final_verification"]["rerun_from_scratch"])
            self.assertEqual(
                set(record["final_verification"]["universe_results"]),
                {"repository", "isolated"},
            )
            self.assertEqual(record["outcome"], "propose-reduction")

    def test_interruption_retains_record_and_removes_temporary_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = AblationFixture(Path(temp_dir))

            def interrupt(_config: CapabilityReviewConfig) -> tuple[dict[str, Any], Path]:
                raise KeyboardInterrupt

            with self.assertRaises(KeyboardInterrupt):
                run_component_ablation(fixture.config, interrupt)

            records = list(fixture.config.output_root.rglob("decision.json"))
            self.assertEqual(len(records), 1)
            record = json.loads(records[0].read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "interrupted")
            self.assertFalse(list(fixture.config.output_root.rglob("candidate-*")))
            self.assertFalse(list(fixture.config.output_root.rglob("temporary-candidates")))


if __name__ == "__main__":
    unittest.main()
