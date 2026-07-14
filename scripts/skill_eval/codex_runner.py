"""Isolated Codex execution and paired behavior grading."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .core import (
    BehaviorCase,
    EvalError,
    git_observations,
    json_dump,
    sanitized_skill_copy,
    snapshot_workspace,
    workspace_delta,
)


def _all_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_strings(nested)


def _load_events(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: {exc}")
            continue
        if isinstance(value, dict):
            events.append(value)
    return events, errors


def _event_summary(
    events: list[dict[str, Any]],
    *,
    activation_marker: str | None,
    activation_name: str | None,
) -> dict[str, Any]:
    final_messages: list[str] = []
    tool_calls = 0
    usage: dict[str, int] = {}
    activated = False
    marker_suffix = activation_marker.replace("\\", "/") if activation_marker else None

    for event in events:
        item = event.get("item")
        if isinstance(item, dict):
            item_type = str(item.get("type", ""))
            if item_type == "agent_message" and isinstance(item.get("text"), str):
                final_messages.append(item["text"])
            if event.get("type") == "item.completed" and item_type not in {
                "agent_message",
                "reasoning",
            }:
                tool_calls += 1
            if item_type in {"skill_call", "skill"} and activation_name:
                activated = activated or any(
                    value == activation_name or value.endswith(f"/{activation_name}")
                    for value in _all_strings(item)
                )
            if marker_suffix and item_type not in {"agent_message", "reasoning"}:
                activated = activated or any(
                    marker_suffix in value.replace("\\", "/") for value in _all_strings(item)
                )
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = {
                key: int(value)
                for key, value in event["usage"].items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
    return {
        "final_response": final_messages[-1] if final_messages else "",
        "tool_calls": tool_calls,
        "usage": usage,
        "activated": activated,
    }


def _scrub(value: str, replacements: dict[str, str]) -> str:
    result = value
    for original, replacement in sorted(
        replacements.items(), key=lambda item: len(item[0]), reverse=True
    ):
        result = result.replace(original, replacement)
    return result


class CodexRunner:
    """Run task and judge turns with a clean Codex home per invocation."""

    def __init__(
        self,
        *,
        skill_dir: Path,
        codex_binary: str,
        model: str | None,
        judge_model: str | None,
        timeout_seconds: int,
        sandbox: str,
        peer_skills: tuple[Path, ...] = (),
    ) -> None:
        resolved_binary = shutil.which(codex_binary)
        if resolved_binary is None:
            raise EvalError(f"Codex executable not found: {codex_binary}")
        self.skill_dir = skill_dir.resolve()
        self.codex_binary = resolved_binary
        self.model = model
        self.judge_model = judge_model or model
        self.timeout_seconds = timeout_seconds
        self.sandbox = sandbox
        self.peer_skills = tuple(path.resolve() for path in peer_skills)
        self.runtime_skill_names = {self.skill_dir.name, *(path.name for path in self.peer_skills)}
        configured_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.auth_source = configured_home / "auth.json"
        if not self.auth_source.is_file():
            raise EvalError(
                f"Codex authentication was not found at {self.auth_source}. "
                "Run `codex login` before evaluating."
            )
        version = subprocess.run(
            [self.codex_binary, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.version = (version.stdout or version.stderr).strip()

    def _prepare_home(
        self, run_dir: Path, *, with_skill: bool, include_peers: bool
    ) -> Path:
        home = run_dir / "codex-home"
        home.mkdir(parents=True, exist_ok=False)
        try:
            (home / "auth.json").symlink_to(self.auth_source)
            skills_to_install = list(self.peer_skills) if include_peers else []
            if with_skill:
                skills_to_install.append(self.skill_dir)
            if skills_to_install:
                skills_dir = home / "skills"
                skills_dir.mkdir()
                for skill in skills_to_install:
                    sanitized_skill_copy(skill, skills_dir / skill.name)
        except Exception:
            shutil.rmtree(home, ignore_errors=True)
            raise
        return home

    def _execute(
        self,
        *,
        run_dir: Path,
        workspace: Path,
        prompt: str,
        with_skill: bool,
        sandbox: str,
        model: str | None,
        output_schema: Path | None = None,
        include_peers: bool = True,
    ) -> dict[str, Any]:
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        home = self._prepare_home(
            run_dir, with_skill=with_skill, include_peers=include_peers
        )
        output_message = run_dir / "final.txt"
        command = [
            self.codex_binary,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--config",
            'shell_environment_policy.inherit="core"',
            "--config",
            'shell_environment_policy.exclude=["CODEX_HOME"]',
            "--config",
            f"shell_environment_policy.set={{ HOME = {json.dumps(str(workspace))} }}",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "--cd",
            str(workspace),
            "--output-last-message",
            str(output_message),
        ]
        if model:
            command.extend(["--model", model])
        if output_schema is not None:
            command.extend(["--output-schema", str(output_schema)])

        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        started = time.monotonic()
        timed_out = False
        try:
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    cwd=workspace,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                stdout = completed.stdout
                stderr = completed.stderr
                exit_code: int | None = completed.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
                stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr or ""
                exit_code = None
        finally:
            shutil.rmtree(home, ignore_errors=True)
        duration = time.monotonic() - started

        events_path = run_dir / "events.jsonl"
        stderr_path = run_dir / "stderr.log"
        events_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        events, parse_errors = _load_events(stdout)
        activation_marker = (
            f"skills/{self.skill_dir.name}/SKILL.md" if with_skill else None
        )
        summary = _event_summary(
            events,
            activation_marker=activation_marker,
            activation_name=self.skill_dir.name if with_skill else None,
        )
        if output_message.is_file():
            summary["final_response"] = output_message.read_text(
                encoding="utf-8", errors="replace"
            )

        status = "timeout" if timed_out else "completed" if exit_code == 0 else "failed"
        return {
            "status": status,
            "exit_code": exit_code,
            "duration_seconds": round(duration, 3),
            "usage": summary["usage"],
            "tool_calls": summary["tool_calls"],
            "activated": summary["activated"],
            "final_response": summary["final_response"],
            "event_parse_errors": parse_errors,
            "events_path": str(events_path),
            "stderr_path": str(stderr_path),
            "prompt_path": str(prompt_path),
            "command": command,
        }

    def run_task(
        self,
        *,
        run_dir: Path,
        workspace_template: Path | None,
        prompt: str,
        case_type: str,
        case_id: str,
        repeat: int,
        condition: str,
    ) -> dict[str, Any]:
        workspace = run_dir / "workspace"
        if workspace_template is None:
            workspace.mkdir(parents=True)
        else:
            shutil.copytree(workspace_template, workspace, symlinks=False)
        before = snapshot_workspace(workspace)
        with_skill = condition == "skill"
        executed = self._execute(
            run_dir=run_dir,
            workspace=workspace,
            prompt=prompt,
            with_skill=with_skill,
            sandbox="read-only" if case_type == "trigger" else self.sandbox,
            model=self.model,
        )
        after = snapshot_workspace(workspace)
        executed.update(
            {
                "case_type": case_type,
                "case_id": case_id,
                "repeat": repeat,
                "condition": condition,
                "workspace": str(workspace),
                "artifact_delta": workspace_delta(before, after),
                "git": git_observations(workspace),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            }
        )
        json_dump(run_dir / "run.json", executed)
        return executed

    def _evidence_bundle(self, run: dict[str, Any]) -> dict[str, Any]:
        events_text = Path(run["events_path"]).read_text(encoding="utf-8", errors="replace")
        events, _errors = _load_events(events_text)
        workspace = str(Path(run["workspace"]).resolve())
        run_root = str(Path(run["workspace"]).parent.resolve())
        replacements = {workspace: "<WORKSPACE>", run_root: "<RUN_ROOT>"}
        commands: list[dict[str, Any]] = []
        activation_markers = {
            f"skills/{name}/SKILL.md" for name in self.runtime_skill_names
        }
        for event in events:
            if event.get("type") != "item.completed" or not isinstance(event.get("item"), dict):
                continue
            item = event["item"]
            if item.get("type") != "command_execution":
                continue
            command = str(item.get("command", ""))
            normalized_command = command.replace("\\", "/")
            if any(marker in normalized_command for marker in activation_markers):
                continue
            commands.append(
                {
                    "command": _scrub(command, replacements),
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status"),
                    "output": _scrub(
                        str(item.get("aggregated_output", ""))[-5000:],
                        replacements,
                    ),
                }
            )
        final = _scrub(run.get("final_response", ""), replacements)
        return {
            "status": run["status"],
            "final_response": final[-20_000:],
            "commands": commands[-40:],
            "artifact_delta": run["artifact_delta"],
            "git": run["git"],
            "duration_seconds": run["duration_seconds"],
            "usage": run["usage"],
            "tool_calls": run["tool_calls"],
        }

    @staticmethod
    def _judge_schema() -> dict[str, Any]:
        check = {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 0},
                "result": {"type": "string", "enum": ["pass", "fail", "unknown"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "string"},
            },
            "required": ["index", "result", "confidence", "evidence"],
            "additionalProperties": False,
        }
        candidate = {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": ["A", "B"]},
                "checks": {"type": "array", "items": check},
                "summary": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["label", "checks", "summary", "strengths", "weaknesses"],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": candidate,
                    "minItems": 2,
                    "maxItems": 2,
                },
                "comparison": {
                    "type": "object",
                    "properties": {
                        "verdict": {
                            "type": "string",
                            "enum": ["A_better", "B_better", "tie", "insufficient"],
                        },
                        "rationale": {"type": "string"},
                        "material_differences": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["verdict", "rationale", "material_differences"],
                    "additionalProperties": False,
                },
            },
            "required": ["candidates", "comparison"],
            "additionalProperties": False,
        }

    def grade_pair(
        self,
        *,
        grade_dir: Path,
        behavior_case: BehaviorCase,
        repeat: int,
        skill_run: dict[str, Any],
        baseline_run: dict[str, Any],
    ) -> dict[str, Any]:
        grade_dir.mkdir(parents=True, exist_ok=True)
        workspace = grade_dir / "workspace"
        workspace.mkdir()
        flip = int(
            hashlib.sha256(f"{behavior_case.id}:{repeat}".encode()).hexdigest(), 16
        ) % 2
        if flip:
            candidates = {
                "A": self._evidence_bundle(baseline_run),
                "B": self._evidence_bundle(skill_run),
            }
            blind_map = {"A": "baseline", "B": "skill"}
        else:
            candidates = {
                "A": self._evidence_bundle(skill_run),
                "B": self._evidence_bundle(baseline_run),
            }
            blind_map = {"A": "skill", "B": "baseline"}

        evidence = {
            "task": behavior_case.prompt,
            "expected_behavior": behavior_case.expected_behavior,
            "checks": [
                {"index": index, "text": check}
                for index, check in enumerate(behavior_case.checks)
            ],
            "candidates": candidates,
            "grading_policy": {
                "pass": "Concrete transcript or artifact evidence proves the check",
                "fail": "Evidence contradicts the check or proves it was not satisfied",
                "unknown": "Available evidence is insufficient; never assume success",
            },
        }
        evidence_path = workspace / "evidence.json"
        schema_path = workspace / "schema.json"
        json_dump(evidence_path, evidence)
        json_dump(schema_path, self._judge_schema())
        prompt = (
            "Act as an evidence-bound, condition-blind evaluator. Read evidence.json. "
            "Grade candidates A and B independently against every numbered check, using the "
            "same standard. Do not reward verbosity, claims of skill use, or plausible intent. "
            "A check passes only when the supplied transcript, Git state, or artifact evidence "
            "proves it. Use unknown when evidence is insufficient. Then compare material task "
            "quality. Return only the required structured result."
        )
        executed = self._execute(
            run_dir=grade_dir,
            workspace=workspace,
            prompt=prompt,
            with_skill=False,
            sandbox="read-only",
            model=self.judge_model,
            output_schema=schema_path,
            include_peers=False,
        )
        judgment: dict[str, Any] | None = None
        parse_error: str | None = None
        if executed["status"] == "completed":
            try:
                parsed = json.loads(executed["final_response"])
                if not isinstance(parsed, dict):
                    raise ValueError("judgment was not an object")
                judgment = parsed
            except (json.JSONDecodeError, ValueError) as exc:
                parse_error = str(exc)

        mapped_grades: dict[str, list[dict[str, Any]]] = {"skill": [], "baseline": []}
        validation_errors: list[str] = []
        if judgment is not None:
            by_label = {
                item.get("label"): item
                for item in judgment.get("candidates", [])
                if isinstance(item, dict)
            }
            for label, condition in blind_map.items():
                candidate = by_label.get(label)
                if not isinstance(candidate, dict):
                    validation_errors.append(f"Missing candidate {label}")
                    continue
                raw_checks = candidate.get("checks", [])
                indexed = {
                    item.get("index"): item
                    for item in raw_checks
                    if isinstance(item, dict) and isinstance(item.get("index"), int)
                }
                for index, check_text in enumerate(behavior_case.checks):
                    item = indexed.get(index)
                    if item is None:
                        validation_errors.append(f"Candidate {label} missing check {index}")
                        mapped_grades[condition].append(
                            {
                                "index": index,
                                "check": check_text,
                                "passed": None,
                                "confidence": 0,
                                "evidence": "Judge omitted this check",
                            }
                        )
                        continue
                    outcome = item.get("result")
                    mapped_grades[condition].append(
                        {
                            "index": index,
                            "check": check_text,
                            "passed": True if outcome == "pass" else False if outcome == "fail" else None,
                            "confidence": item.get("confidence", 0),
                            "evidence": item.get("evidence", ""),
                        }
                    )

        status = (
            "completed"
            if executed["status"] == "completed"
            and judgment is not None
            and not validation_errors
            else "invalid"
            if executed["status"] == "completed"
            else executed["status"]
        )
        result = {
            "status": status,
            "blind_map": blind_map,
            "grades": mapped_grades,
            "judgment": judgment,
            "comparison": judgment.get("comparison") if judgment else None,
            "parse_error": parse_error,
            "validation_errors": validation_errors,
            "duration_seconds": executed["duration_seconds"],
            "usage": executed["usage"],
            "events_path": executed["events_path"],
            "stderr_path": executed["stderr_path"],
        }
        json_dump(grade_dir / "grading.json", result)
        return result
