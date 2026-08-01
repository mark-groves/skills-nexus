"""Harness-neutral contracts and the compatibility factory for skill evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .core import EvaluationCondition


@dataclass(frozen=True)
class HarnessCapabilities:
    """Evidence and execution features exposed by a harness adapter."""

    task_execution: bool
    judgment_execution: bool
    activation_evidence: bool
    usage_telemetry: bool
    structured_output: bool


@dataclass(frozen=True)
class UnavailableEvidence:
    """Typed absence for evidence a harness cannot provide."""

    reason: str


@dataclass(frozen=True)
class TaskRequest:
    run_dir: Path
    workspace_template: Path | None
    prompt: str
    case_type: str
    case_id: str
    repeat: int
    condition: EvaluationCondition


@dataclass(frozen=True)
class JudgmentRequest:
    run_dir: Path
    workspace: Path
    prompt: str
    output_schema: Path


class TaskHarness(Protocol):
    id: str
    version: str
    capabilities: HarnessCapabilities
    conditions: tuple[EvaluationCondition, ...]
    peer_skills: tuple[Path, ...]

    def run_task(self, request: TaskRequest) -> Mapping[str, Any]: ...


class JudgeHarness(Protocol):
    id: str
    version: str
    capabilities: HarnessCapabilities

    def execute_judgment(self, request: JudgmentRequest) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class Harnesses:
    task: TaskHarness
    judge: JudgeHarness


class HarnessFactory(Protocol):
    def __call__(
        self,
        *,
        conditions: tuple[EvaluationCondition, ...],
        codex_binary: str,
        model: str | None,
        judge_model: str | None,
        timeout_seconds: int,
        sandbox: str,
        peer_skills: tuple[Path, ...],
        deadline_seconds: int | None,
    ) -> Harnesses: ...


def default_harness_factory(
    *,
    conditions: tuple[EvaluationCondition, ...],
    codex_binary: str,
    model: str | None,
    judge_model: str | None,
    timeout_seconds: int,
    sandbox: str,
    peer_skills: tuple[Path, ...],
    deadline_seconds: int | None,
) -> Harnesses:
    """Build the existing Codex task and judge path behind neutral contracts.

    The lazy import keeps evaluator orchestration independent of the Codex
    implementation. An explicit adapter registry remains follow-up work.
    """

    from .codex_runner import CodexRunner

    runner = CodexRunner(
        conditions=conditions,
        codex_binary=codex_binary,
        model=model,
        judge_model=judge_model,
        timeout_seconds=timeout_seconds,
        sandbox=sandbox,
        peer_skills=peer_skills,
        deadline_seconds=deadline_seconds,
    )
    return Harnesses(task=runner, judge=runner)
