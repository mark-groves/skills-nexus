from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_DIR / "scripts" / "eval_skills.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))
SPEC = importlib.util.spec_from_file_location("eval_skills_harness_boundary", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
eval_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_skills)

from skill_eval.core import BehaviorCase, BehaviorCheck, EvaluationCondition  # noqa: E402
from skill_eval.engine import execute_in_workspace, materialize_unavailable  # noqa: E402
from skill_eval.evidence import build_evidence_bundle  # noqa: E402
from skill_eval.harness import (  # noqa: E402
    HarnessCapabilities,
    Harnesses,
    JudgmentRequest,
    TaskRequest,
    UnavailableEvidence,
)
from skill_eval.judging import grade_behavior, validate_judgment  # noqa: E402


class FakeThirdHarness:
    id = "third-harness"
    version = "third-harness 1.0"
    capabilities = HarnessCapabilities(
        task_execution=True,
        judgment_execution=True,
        activation_evidence=False,
        usage_telemetry=False,
        structured_output=False,
    )

    def __init__(self, *, conditions, peer_skills) -> None:
        self.conditions = conditions
        self.peer_skills = peer_skills

    def run_task(self, request: TaskRequest) -> dict[str, Any]:
        def execute(workspace: Path) -> dict[str, Any]:
            (workspace / "result.txt").write_text("third harness result\n", encoding="utf-8")
            events_path = request.run_dir / "events.jsonl"
            stderr_path = request.run_dir / "stderr.log"
            events_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "status": "completed",
                "exit_code": 0,
                "duration_seconds": 0.01,
                "usage": UnavailableEvidence("third harness does not expose token usage"),
                "tool_calls": UnavailableEvidence("third harness does not expose tool calls"),
                "activated": UnavailableEvidence("third harness has no activation signal"),
                "final_response": "third harness result",
                "events_path": str(events_path),
                "stderr_path": str(stderr_path),
                "prompt_path": str(request.run_dir / "prompt.txt"),
                "runtime_home": "",
            }

        run = execute_in_workspace(request, execute)
        run["evidence"] = build_evidence_bundle(
            run,
            commands=(),
            runtime_skill_names=set(),
            runtime_instruction_texts=(),
        )
        return run

    def execute_judgment(self, request: JudgmentRequest) -> dict[str, Any]:
        evidence = json.loads((request.workspace / "evidence.json").read_text(encoding="utf-8"))
        labels = tuple(evidence["candidates"])
        candidates = [
            {
                "label": label,
                "checks": [
                    {
                        "index": check["index"],
                        "result": "pass",
                        "confidence": 1.0,
                        "evidence": "normalized result evidence is present",
                    }
                    for check in evidence["checks"]
                ],
                "summary": "supported",
                "strengths": ["normalized evidence"],
                "weaknesses": [],
            }
            for label in labels
        ]
        judgment: dict[str, Any] = {"candidates": candidates}
        if len(labels) == 2:
            judgment["comparison"] = {
                "verdict": "tie",
                "rationale": "both normalized results satisfy the check",
                "material_differences": [],
            }
        return {
            "status": "completed",
            "final_response": json.dumps(judgment),
            "duration_seconds": 0.01,
            "usage": UnavailableEvidence("third harness does not expose judge usage"),
            "events_path": UnavailableEvidence("third harness has no event stream"),
            "stderr_path": UnavailableEvidence("third harness has no stderr artifact"),
        }


class HarnessBoundaryTests(unittest.TestCase):
    def _write_repo(self, root: Path) -> Path:
        repo = root / "repo"
        skill = repo / "skills" / "demo"
        eval_dir = repo / "evals" / "demo"
        skill.mkdir(parents=True)
        eval_dir.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Use for demo tasks.\n---\n\n# Demo\n",
            encoding="utf-8",
        )
        (eval_dir / "evals.json").write_text(
            json.dumps(
                {
                    "skill_name": "demo",
                    "trigger_evals": [],
                    "behavior_evals": [
                        {
                            "id": "behavior",
                            "prompt": "produce a result",
                            "expected_behavior": "Produces a result.",
                            "fixtures": [],
                            "checks": [
                                {
                                    "id": "protected-result",
                                    "text": "Produces a result",
                                    "class": "safety",
                                    "gate": "hard",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return repo

    def test_fake_third_harness_runs_end_to_end_without_orchestration_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._write_repo(Path(temp_dir))
            output_root = repo / ".skill-evals-test"
            created: list[FakeThirdHarness] = []

            def factory(**kwargs):
                harness = FakeThirdHarness(
                    conditions=kwargs["conditions"],
                    peer_skills=kwargs["peer_skills"],
                )
                created.append(harness)
                return Harnesses(task=harness, judge=harness)

            args = eval_skills.build_parser().parse_args(
                [
                    "--repo-root",
                    str(repo),
                    "--skill",
                    "demo",
                    "--suite",
                    "behavior",
                    "--output-root",
                    str(output_root),
                ]
            )
            with contextlib.redirect_stdout(io.StringIO()):
                result, output_dir = eval_skills.run_evaluation(args, harness_factory=factory)
            self.assertTrue((output_dir / "report.md").is_file())

        self.assertEqual(len(created), 1)
        self.assertEqual(result["runtime"]["adapter"], "third-harness")
        behavior = result["behavior"]["results"][0]
        self.assertEqual(behavior["judge"]["status"], "completed")
        self.assertTrue(behavior["grades"]["skill"][0]["passed"])
        self.assertIsNone(behavior["skill_run"]["usage"])
        self.assertIn("usage", behavior["skill_run"]["unavailable_evidence"])

    def test_plan_mode_does_not_construct_a_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._write_repo(Path(temp_dir))
            args = eval_skills.build_parser().parse_args(
                ["--repo-root", str(repo), "--skill", "demo", "--plan"]
            )
            factory = mock.Mock()

            with contextlib.redirect_stdout(io.StringIO()):
                result, output = eval_skills.run_evaluation(args, harness_factory=factory)

        self.assertEqual(result, {})
        self.assertEqual(output, Path())
        factory.assert_not_called()

    def test_unavailable_evidence_is_null_with_an_explicit_reason(self) -> None:
        value, reasons = materialize_unavailable(
            {"usage": UnavailableEvidence("unsupported telemetry")}
        )

        self.assertEqual(value, {"usage": None})
        self.assertEqual(reasons, {"usage": "unsupported telemetry"})

    def test_duplicate_judge_indices_fail_local_validation(self) -> None:
        candidate = {
            "label": "A",
            "checks": [
                {"index": 0, "result": "pass", "confidence": 1.0, "evidence": "one"},
                {"index": 0, "result": "pass", "confidence": 1.0, "evidence": "two"},
            ],
            "summary": "invalid",
            "strengths": [],
            "weaknesses": [],
        }
        other = {**candidate, "label": "B"}
        judgment = {
            "candidates": [candidate, other],
            "comparison": {
                "verdict": "tie",
                "rationale": "invalid",
                "material_differences": [],
            },
        }

        errors = validate_judgment(judgment, labels=("A", "B"), check_count=2)

        self.assertTrue(any("duplicate check index" in error for error in errors))

    def test_unknown_protected_judgment_maps_to_unknown_not_pass(self) -> None:
        conditions = (
            EvaluationCondition("skill", None, None, "demo", "Skill"),
            EvaluationCondition("baseline", None, None, "demo", "Baseline"),
        )
        behavior_case = BehaviorCase(
            id="protected",
            prompt="preserve the boundary",
            expected_behavior="The boundary is preserved.",
            fixtures=(),
            checks=(
                BehaviorCheck(
                    "protected-boundary",
                    "Preserves the protected boundary",
                    "safety",
                    "hard",
                ),
            ),
        )

        class UnknownJudge:
            id = "unknown-judge"
            version = "1"
            capabilities = FakeThirdHarness.capabilities

            def execute_judgment(self, request: JudgmentRequest) -> dict[str, Any]:
                evidence = json.loads(
                    (request.workspace / "evidence.json").read_text(encoding="utf-8")
                )
                labels = tuple(evidence["candidates"])
                candidates = [
                    {
                        "label": label,
                        "checks": [
                            {
                                "index": 0,
                                "result": "unknown",
                                "confidence": 0.0,
                                "evidence": "protected evidence is unavailable",
                            }
                        ],
                        "summary": "unknown",
                        "strengths": [],
                        "weaknesses": ["missing protected evidence"],
                    }
                    for label in labels
                ]
                return {
                    "status": "completed",
                    "final_response": json.dumps(
                        {
                            "candidates": candidates,
                            "comparison": {
                                "verdict": "insufficient",
                                "rationale": "protected evidence is unavailable",
                                "material_differences": [],
                            },
                        }
                    ),
                    "duration_seconds": 0.01,
                    "usage": UnavailableEvidence("unsupported"),
                    "events_path": UnavailableEvidence("unsupported"),
                    "stderr_path": UnavailableEvidence("unsupported"),
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            result = grade_behavior(
                UnknownJudge(),
                conditions=conditions,
                grade_dir=Path(temp_dir) / "judge",
                behavior_case=behavior_case,
                repeat=1,
                evidence_by_condition={
                    condition.id: {"status": "completed"} for condition in conditions
                },
            )

        self.assertEqual(result["status"], "completed")
        for condition in conditions:
            grade = result["grades"][condition.id][0]
            self.assertEqual(grade["gate"], "hard")
            self.assertIsNone(grade["passed"])


if __name__ == "__main__":
    unittest.main()
