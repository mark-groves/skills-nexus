"""Codex task, judge, event, and construction adapter responsibilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from ..codex_runner import CodexRunner
from ..harness import HarnessCapabilities, JudgmentRequest, TaskRequest
from .events import CodexEventParser
from .registry import HarnessAdapterRegistry, HarnessBuildContext


class CodexTaskHarness:
    """Expose Codex task execution through the neutral task contract."""

    id = "codex"
    capabilities = HarnessCapabilities(
        task_execution=True,
        judgment_execution=False,
        activation_evidence=True,
        usage_telemetry=True,
        structured_output=True,
    )

    def __init__(self, runner: CodexRunner) -> None:
        self._runner = runner
        self.version = runner.version
        self.conditions = runner.conditions
        self.peer_skills = runner.peer_skills

    def run_task(self, request: TaskRequest) -> Mapping[str, Any]:
        return self._runner.run_task(request)


class CodexJudgeHarness:
    """Expose Codex structured judging through the neutral judge contract."""

    id = "codex"
    capabilities = HarnessCapabilities(
        task_execution=False,
        judgment_execution=True,
        activation_evidence=False,
        usage_telemetry=True,
        structured_output=True,
    )

    def __init__(self, runner: CodexRunner) -> None:
        self._runner = runner
        self.version = runner.version

    def execute_judgment(self, request: JudgmentRequest) -> Mapping[str, Any]:
        return self._runner.execute_judgment(request)


class CodexHarnessFactory:
    """Build role-specific Codex harnesses around one shared runtime backend."""

    _shared_key = "codex-runtime"

    def _runner(self, context: HarnessBuildContext) -> CodexRunner:
        def build() -> object:
            return CodexRunner(
                conditions=context.conditions,
                codex_binary=context.binary_overrides.get(self.id, self.id),
                model=context.task_model,
                judge_model=context.judge_model,
                timeout_seconds=context.timeout_seconds,
                sandbox=context.sandbox,
                peer_skills=context.peer_skills,
                deadline_seconds=context.deadline_seconds,
            )

        return cast(CodexRunner, context.shared(self._shared_key, build))

    @property
    def id(self) -> str:
        return "codex"

    def build_task(self, context: HarnessBuildContext) -> CodexTaskHarness:
        return CodexTaskHarness(self._runner(context))

    def build_judge(self, context: HarnessBuildContext) -> CodexJudgeHarness:
        return CodexJudgeHarness(self._runner(context))


def register_codex_adapters(
    task_registry: HarnessAdapterRegistry[Any],
    judge_registry: HarnessAdapterRegistry[Any],
) -> None:
    """Register Codex for both roles without leaking it into orchestration."""

    factory = CodexHarnessFactory()
    task_registry.register(factory.id, factory.build_task)
    judge_registry.register(factory.id, factory.build_judge)


__all__ = [
    "CodexEventParser",
    "CodexHarnessFactory",
    "CodexJudgeHarness",
    "CodexTaskHarness",
]
