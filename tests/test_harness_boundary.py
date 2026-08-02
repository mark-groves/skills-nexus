from __future__ import annotations

import concurrent.futures
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, cast
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_DIR / "scripts" / "eval_skills.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))
SPEC = importlib.util.spec_from_file_location("eval_skills_harness_boundary", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
eval_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_skills)

from skill_eval.adapters import codex as codex_adapter  # noqa: E402
from skill_eval.adapters import registry as adapter_registry  # noqa: E402
from skill_eval.adapters.codex import (  # noqa: E402
    CodexEventParser,
    CodexJudgeHarness,
    CodexTaskHarness,
)
from skill_eval.adapters.registry import (  # noqa: E402
    JUDGE_ADAPTER_REGISTRY,
    TASK_ADAPTER_REGISTRY,
    HarnessAdapterRegistry,
    validate_adapter_selection,
)
from skill_eval.core import BehaviorCase, BehaviorCheck, EvaluationCondition  # noqa: E402
from skill_eval.engine import execute_in_workspace, materialize_unavailable  # noqa: E402
from skill_eval.evidence import build_evidence_bundle  # noqa: E402
from skill_eval.harness import (  # noqa: E402
    HarnessCapabilities,
    Harnesses,
    JudgmentRequest,
    TaskRequest,
    UnavailableEvidence,
    default_harness_factory,
)
from skill_eval.judging import grade_behavior, validate_judgment  # noqa: E402


class FakeThirdHarness:
    id = "third-harness"
    version = "third-harness 1.0"
    reported_model: str | UnavailableEvidence = "third-native-model"
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
        self.assertEqual(result["runtime"]["task_adapter"], "third-harness")
        self.assertEqual(result["runtime"]["task_adapter_version"], "third-harness 1.0")
        self.assertEqual(result["runtime"]["judge_adapter"], "third-harness")
        self.assertEqual(result["runtime"]["judge_adapter_version"], "third-harness 1.0")
        self.assertEqual(result["runtime"]["task_model_reported"], "third-native-model")
        self.assertEqual(result["runtime"]["judge_model_reported"], "third-native-model")
        self.assertNotIn("unavailable_evidence", result["runtime"])
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

    def test_codex_is_the_default_for_both_adapter_roles(self) -> None:
        args = eval_skills.build_parser().parse_args(["--skill", "demo"])

        self.assertEqual(args.task_adapter, "codex")
        self.assertEqual(args.judge_adapter, "codex")
        validate_adapter_selection(args.task_adapter, args.judge_adapter)
        self.assertEqual(TASK_ADAPTER_REGISTRY.ids, ("codex",))
        self.assertEqual(JUDGE_ADAPTER_REGISTRY.ids, ("codex",))

    def test_builtin_registration_serializes_concurrent_first_use(self) -> None:
        task_registry = HarnessAdapterRegistry("task")
        judge_registry = HarnessAdapterRegistry("judge")
        barrier = threading.Barrier(8)
        call_lock = threading.Lock()
        calls = 0
        original_register = codex_adapter.register_codex_adapters

        def slow_register(*args: Any) -> None:
            nonlocal calls
            with call_lock:
                calls += 1
            time.sleep(0.02)
            original_register(*args)

        def validate() -> None:
            barrier.wait()
            adapter_registry.validate_adapter_selection("codex", "codex")

        with (
            mock.patch.object(adapter_registry, "TASK_ADAPTER_REGISTRY", task_registry),
            mock.patch.object(adapter_registry, "JUDGE_ADAPTER_REGISTRY", judge_registry),
            mock.patch.object(adapter_registry, "_BUILTINS_REGISTERED", False),
            mock.patch.object(codex_adapter, "register_codex_adapters", side_effect=slow_register),
            concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor,
        ):
            futures = [executor.submit(validate) for _ in range(8)]
            for future in futures:
                future.result()

        self.assertEqual(calls, 1)
        self.assertEqual(task_registry.ids, ("codex",))
        self.assertEqual(judge_registry.ids, ("codex",))

    def test_unknown_adapter_fails_in_plan_mode_before_harness_construction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._write_repo(Path(temp_dir))
            factory = mock.Mock()
            for flag, role in (
                ("--task-adapter", "task"),
                ("--judge-adapter", "judge"),
            ):
                with self.subTest(role=role):
                    args = eval_skills.build_parser().parse_args(
                        [
                            "--repo-root",
                            str(repo),
                            "--skill",
                            "demo",
                            "--plan",
                            flag,
                            "missing",
                        ]
                    )
                    with self.assertRaisesRegex(
                        eval_skills.EvalError,
                        rf"Unknown {role} adapter 'missing'.*codex",
                    ):
                        eval_skills.run_evaluation(args, harness_factory=factory)

        factory.assert_not_called()

    def test_codex_factory_builds_role_harnesses_around_one_runner(self) -> None:
        conditions = (
            EvaluationCondition("skill", None, None, "demo", "Skill"),
            EvaluationCondition("baseline", None, None, "demo", "Baseline"),
        )
        runner = mock.Mock(
            version="codex 1.0",
            conditions=conditions,
            peer_skills=(),
        )
        with mock.patch("skill_eval.adapters.codex.CodexRunner", return_value=runner) as create:
            harnesses = default_harness_factory(
                task_adapter="codex",
                judge_adapter="codex",
                conditions=conditions,
                codex_binary="custom-codex",
                model="task-model",
                judge_model="judge-model",
                timeout_seconds=30,
                sandbox="workspace-write",
                peer_skills=(),
                deadline_seconds=60,
            )

        create.assert_called_once_with(
            conditions=conditions,
            codex_binary="custom-codex",
            model="task-model",
            judge_model="judge-model",
            timeout_seconds=30,
            sandbox="workspace-write",
            peer_skills=(),
            deadline_seconds=60,
        )
        self.assertEqual(harnesses.task.id, "codex")
        self.assertEqual(harnesses.judge.id, "codex")
        self.assertIsInstance(harnesses.task.reported_model, UnavailableEvidence)
        self.assertIsInstance(harnesses.judge.reported_model, UnavailableEvidence)
        self.assertIs(cast(CodexTaskHarness, harnesses.task)._runner, runner)
        self.assertIs(cast(CodexJudgeHarness, harnesses.judge)._runner, runner)

    def test_codex_event_parser_keeps_malformed_evidence_explicit(self) -> None:
        events, errors = CodexEventParser.load(
            '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\nnot-json\n'
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("line 2", errors[0])
        summary = CodexEventParser.summarize(
            events,
            activation_marker=None,
            activation_name=None,
        )
        self.assertEqual(summary["final_response"], "done")
        self.assertEqual(summary["tool_calls"], 0)

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
            reported_model: str | UnavailableEvidence = UnavailableEvidence(
                "unknown judge does not expose its model"
            )
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
