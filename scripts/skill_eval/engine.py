"""Common task scheduling and workspace-observation boundaries."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .core import EvalError, git_observations, snapshot_workspace, workspace_delta
from .harness import TaskHarness, TaskRequest, UnavailableEvidence


def materialize_unavailable(value: object) -> tuple[object, dict[str, str]]:
    """Serialize typed unavailable evidence as JSON null plus explicit reasons."""

    reasons: dict[str, str] = {}

    def visit(item: object, path: str) -> object:
        if isinstance(item, UnavailableEvidence):
            reasons[path or "value"] = item.reason
            return None
        if isinstance(item, Mapping):
            return {
                str(key): visit(nested, f"{path}.{key}" if path else str(key))
                for key, nested in item.items()
            }
        if isinstance(item, tuple):
            return [visit(nested, f"{path}[{index}]") for index, nested in enumerate(item)]
        if isinstance(item, list):
            return [visit(nested, f"{path}[{index}]") for index, nested in enumerate(item)]
        return item

    return visit(value, ""), reasons


def run_task(harness: TaskHarness, request: TaskRequest) -> dict[str, Any]:
    """Invoke one task harness and preserve typed missing-evidence semantics."""

    configured_condition = next(
        (condition for condition in harness.conditions if condition.id == request.condition.id),
        None,
    )
    if configured_condition != request.condition:
        raise EvalError("task condition must exactly match a configured evaluation condition")
    raw = harness.run_task(request)
    if not isinstance(raw, Mapping):
        raise EvalError("task harness returned a non-object result")
    materialized, reasons = materialize_unavailable(raw)
    if not isinstance(materialized, dict):
        raise EvalError("task harness returned a non-object result")
    if reasons:
        existing = materialized.get("unavailable_evidence")
        unavailable = dict(existing) if isinstance(existing, dict) else {}
        unavailable.update(reasons)
        materialized["unavailable_evidence"] = unavailable
    status = materialized.get("status")
    if status not in {
        "completed",
        "failed",
        "timeout",
        "budget_exceeded",
        "cancelled",
        "incomplete",
        "invalid",
        "unavailable",
    }:
        raise EvalError(f"task harness returned an invalid status: {status!r}")
    return materialized


def execute_in_workspace(
    request: TaskRequest,
    execute: Callable[[Path], Mapping[str, Any]],
) -> dict[str, Any]:
    """Create, observe, and preserve a fresh task workspace around an adapter call."""

    request.run_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(tempfile.mkdtemp(prefix="skill-eval-task-workspace-"))
    workspace = workspace_root / "workspace"
    preserved_workspace = request.run_dir / "workspace"
    if preserved_workspace.exists():
        shutil.rmtree(workspace_root, ignore_errors=True)
        raise EvalError(f"Run workspace already exists: {preserved_workspace}")
    artifacts: dict[str, Any] = {"created": [], "modified": [], "deleted": []}
    git: dict[str, Any] = {"available": False}
    try:
        if request.workspace_template is None:
            workspace.mkdir()
        else:
            shutil.copytree(request.workspace_template, workspace, symlinks=False)
        before = snapshot_workspace(workspace)
        executed = dict(execute(workspace))
        after = snapshot_workspace(workspace)
        artifacts = workspace_delta(before, after)
        git = git_observations(workspace)
    finally:
        if workspace.exists():
            shutil.move(str(workspace), preserved_workspace)
        shutil.rmtree(workspace_root, ignore_errors=True)
    executed.update(
        {
            "case_type": request.case_type,
            "case_id": request.case_id,
            "repeat": request.repeat,
            "condition": request.condition.id,
            "workspace": str(preserved_workspace),
            "execution_workspace": str(workspace),
            "artifact_delta": artifacts,
            "git": git,
            "prompt_sha256": hashlib.sha256(request.prompt.encode()).hexdigest(),
        }
    )
    return executed
