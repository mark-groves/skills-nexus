"""Isolated Codex execution and paired behavior grading."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

from .core import (
    BehaviorCase,
    EvalError,
    EvaluationCondition,
    json_dump,
    runtime_skill_copy,
    skill_instructions,
)
from .engine import execute_in_workspace
from .evidence import (
    _all_strings,
    build_evidence_bundle,
)
from .evidence import (
    _scrub as _scrub,
)
from .harness import HarnessCapabilities, JudgmentRequest, TaskRequest
from .judging import grade_behavior, judgment_schema


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


class CodexRunner:
    """Run task and judge turns with a clean Codex home per invocation."""

    id = "codex"
    capabilities = HarnessCapabilities(
        task_execution=True,
        judgment_execution=True,
        activation_evidence=True,
        usage_telemetry=True,
        structured_output=True,
    )

    def __init__(
        self,
        *,
        conditions: tuple[EvaluationCondition, ...],
        codex_binary: str,
        model: str | None,
        judge_model: str | None,
        timeout_seconds: int,
        sandbox: str,
        peer_skills: tuple[Path, ...] = (),
        deadline_seconds: int | None = None,
    ) -> None:
        resolved_binary = shutil.which(codex_binary)
        if resolved_binary is None:
            raise EvalError(f"Codex executable not found: {codex_binary}")
        if len(conditions) not in {2, 3}:
            raise EvalError("evaluation requires two or three conditions")
        if len({condition.id for condition in conditions}) != len(conditions):
            raise EvalError("evaluation condition ids must be unique")
        self.conditions = conditions
        self.codex_binary = resolved_binary
        self.model = model
        self.judge_model = judge_model or model
        self.timeout_seconds = timeout_seconds
        self.deadline_monotonic = (
            time.monotonic() + deadline_seconds if deadline_seconds is not None else None
        )
        self.sandbox = sandbox
        self.peer_skills = tuple(path.resolve() for path in peer_skills)
        runtime_conditions = tuple(
            condition for condition in conditions if condition.runtime_skill_dir is not None
        )
        self.runtime_skill_names = {
            *(condition.installation_name for condition in runtime_conditions),
            *(path.name for path in self.peer_skills),
        }
        runtime_skills = (
            tuple(
                runtime_skill
                for condition in runtime_conditions
                if (runtime_skill := condition.runtime_skill_dir) is not None
            )
            + self.peer_skills
        )
        self.runtime_instruction_texts = tuple(skill_instructions(path) for path in runtime_skills)
        configured_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.auth_source = configured_home / "auth.json"
        api_key = os.environ.get("CODEX_API_KEY")
        if api_key:
            auth_payload = {
                "auth_mode": "apikey",
                "OPENAI_API_KEY": api_key,
            }
        elif self.auth_source.is_file():
            try:
                auth_payload = json.loads(self.auth_source.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EvalError(f"Codex authentication could not be read: {exc}") from exc
        else:
            raise EvalError(
                f"Codex authentication was not found at {self.auth_source}, and "
                "CODEX_API_KEY is not set. Run `codex login` or provide a key before "
                "evaluating."
            )
        if not isinstance(auth_payload, dict):
            raise EvalError("Codex authentication must be a JSON object")
        tokens = auth_payload.get("tokens")
        if auth_payload.get("auth_mode") in {None, "chatgpt", "chatgptAuthTokens"} and isinstance(
            tokens, dict
        ):
            # External-token mode prevents this isolated copy from rotating the user's
            # refresh token while still supporting authenticated evaluator turns.
            auth_payload["auth_mode"] = "chatgptAuthTokens"
            tokens["refresh_token"] = ""
        self.auth_payload = json.dumps(auth_payload)
        version = subprocess.run(
            [self.codex_binary, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.version = (version.stdout or version.stderr).strip()

    def _prepare_home(
        self,
        *,
        condition: EvaluationCondition | None,
        include_peers: bool,
    ) -> Path:
        home = Path(tempfile.mkdtemp(prefix="skill-eval-codex-home-"))
        try:
            skills_to_install = (
                [(skill, skill.name) for skill in self.peer_skills] if include_peers else []
            )
            if condition is not None and condition.runtime_skill_dir is not None:
                skills_to_install.append((condition.runtime_skill_dir, condition.installation_name))
            if skills_to_install:
                skills_dir = home / ".agents" / "skills"
                skills_dir.mkdir(parents=True)
                for skill, installation_name in skills_to_install:
                    runtime_skill_copy(skill, skills_dir / installation_name)
        except Exception:
            shutil.rmtree(home, ignore_errors=True)
            raise
        return home

    @staticmethod
    def _capture_process_output(
        stream: TextIO,
        chunks: list[str],
        auth_path: Path | None = None,
    ) -> None:
        """Capture a process stream and remove startup auth before agent commands run."""
        try:
            for line in stream:
                chunks.append(line)
                if auth_path is None:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "turn.started":
                    auth_path.unlink(missing_ok=True)
        finally:
            stream.close()

    def _execute(
        self,
        *,
        run_dir: Path,
        workspace: Path,
        prompt: str,
        condition: EvaluationCondition | None,
        sandbox: str,
        model: str | None,
        output_schema: Path | None = None,
        include_peers: bool = True,
    ) -> dict[str, Any]:
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        home = self._prepare_home(condition=condition, include_peers=include_peers)
        auth_path = home / "auth.json"
        try:
            descriptor = os.open(
                auth_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(self.auth_payload)
        except Exception:
            shutil.rmtree(home, ignore_errors=True)
            raise
        output_message = run_dir / "final.txt"
        git_ceiling = str(workspace.parent.resolve())
        command = [
            self.codex_binary,
            "--ask-for-approval",
            "never",
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
            "shell_environment_policy.set={ "
            f"HOME = {json.dumps(str(workspace))}, "
            f"GIT_CEILING_DIRECTORIES = {json.dumps(git_ceiling)} }}",
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
        env.pop("CODEX_API_KEY", None)
        env["CODEX_HOME"] = str(home)
        env["HOME"] = str(home)
        env["GIT_CEILING_DIRECTORIES"] = git_ceiling
        started = time.monotonic()
        timed_out = False
        budget_exceeded = False
        process: subprocess.Popen[str] | None = None
        stdout_thread: threading.Thread | None = None
        stderr_thread: threading.Thread | None = None
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        exit_code: int | None
        try:
            try:
                remaining = (
                    self.deadline_monotonic - time.monotonic()
                    if self.deadline_monotonic is not None
                    else None
                )
                if remaining is not None and remaining <= 0:
                    budget_exceeded = True
                    exit_code = None
                else:
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=workspace,
                        env=env,
                        text=True,
                    )
                    if process.stdin is None or process.stdout is None or process.stderr is None:
                        raise EvalError("Codex process pipes were not available")
                    stdout_thread = threading.Thread(
                        target=self._capture_process_output,
                        args=(process.stdout, stdout_chunks, auth_path),
                        daemon=True,
                    )
                    stderr_thread = threading.Thread(
                        target=self._capture_process_output,
                        args=(process.stderr, stderr_chunks),
                        daemon=True,
                    )
                    stdout_thread.start()
                    stderr_thread.start()
                    try:
                        process.stdin.write(prompt)
                        process.stdin.flush()
                    except BrokenPipeError:
                        pass
                    finally:
                        process.stdin.close()
                    turn_timeout = (
                        min(self.timeout_seconds, max(0.001, remaining))
                        if remaining is not None
                        else self.timeout_seconds
                    )
                    process.wait(timeout=turn_timeout)
                    exit_code = process.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                budget_exceeded = (
                    self.deadline_monotonic is not None
                    and time.monotonic() >= self.deadline_monotonic
                )
                if process is not None:
                    process.kill()
                    process.wait()
                exit_code = None
            except BaseException:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
                raise
        finally:
            auth_path.unlink(missing_ok=True)
            if stdout_thread is not None:
                stdout_thread.join()
            if stderr_thread is not None:
                stderr_thread.join()
            shutil.rmtree(home, ignore_errors=True)
        duration = time.monotonic() - started
        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)

        events_path = run_dir / "events.jsonl"
        stderr_path = run_dir / "stderr.log"
        events_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        events, parse_errors = _load_events(stdout)
        runtime_installed = condition is not None and condition.runtime_skill_dir is not None
        activation_marker = (
            f"skills/{condition.installation_name}/SKILL.md"
            if runtime_installed and condition is not None
            else None
        )
        summary = _event_summary(
            events,
            activation_marker=activation_marker,
            activation_name=condition.installation_name
            if runtime_installed and condition is not None
            else None,
        )
        if output_message.is_file():
            summary["final_response"] = output_message.read_text(encoding="utf-8", errors="replace")

        status = (
            "budget_exceeded"
            if budget_exceeded
            else "timeout"
            if timed_out
            else "completed"
            if exit_code == 0
            else "failed"
        )
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
            "runtime_home": str(home),
        }

    def run_task(
        self,
        request: TaskRequest | None = None,
        *,
        run_dir: Path | None = None,
        workspace_template: Path | None = None,
        prompt: str | None = None,
        case_type: str | None = None,
        case_id: str | None = None,
        repeat: int | None = None,
        condition: EvaluationCondition | None = None,
    ) -> dict[str, Any]:
        if request is None:
            if (
                run_dir is None
                or prompt is None
                or case_type is None
                or case_id is None
                or repeat is None
                or condition is None
            ):
                raise TypeError("run_task requires a TaskRequest or the complete legacy arguments")
            request = TaskRequest(
                run_dir=run_dir,
                workspace_template=workspace_template,
                prompt=prompt,
                case_type=case_type,
                case_id=case_id,
                repeat=repeat,
                condition=condition,
            )
        condition = request.condition
        configured_condition = next(
            (configured for configured in self.conditions if configured.id == condition.id),
            None,
        )
        if configured_condition != condition:
            raise EvalError("task condition must exactly match a configured evaluation condition")
        executed = execute_in_workspace(
            request,
            lambda workspace: self._execute(
                run_dir=request.run_dir,
                workspace=workspace,
                prompt=request.prompt,
                condition=condition,
                sandbox="read-only" if request.case_type == "trigger" else self.sandbox,
                model=self.model,
            ),
        )
        executed["evidence"] = self._evidence_bundle(executed)
        json_dump(request.run_dir / "run.json", executed)
        return executed

    def _evidence_bundle(self, run: dict[str, Any]) -> dict[str, Any]:
        events_path = Path(str(run.get("events_path", "")))
        events_text = (
            events_path.read_text(encoding="utf-8", errors="replace")
            if events_path.is_file()
            else ""
        )
        events, _errors = _load_events(events_text)
        commands: list[dict[str, Any]] = []
        for event in events:
            if event.get("type") != "item.completed" or not isinstance(event.get("item"), dict):
                continue
            item = event["item"]
            if item.get("type") != "command_execution":
                continue
            commands.append(
                {
                    "command": item.get("command", ""),
                    "exit_code": item.get("exit_code"),
                    "status": item.get("status"),
                    "output": item.get("aggregated_output", ""),
                }
            )
        return build_evidence_bundle(
            run,
            commands=commands,
            runtime_skill_names=getattr(self, "runtime_skill_names", set()),
            runtime_instruction_texts=getattr(self, "runtime_instruction_texts", ()),
            runtime_home_label="<CODEX_HOME>",
        )

    @staticmethod
    def _judge_schema(labels: tuple[str, ...] = ("A", "B")) -> dict[str, Any]:
        return judgment_schema(labels)

    def execute_judgment(self, request: JudgmentRequest) -> Mapping[str, Any]:
        """Execute the Codex-specific structured-output turn only."""

        return self._execute(
            run_dir=request.run_dir,
            workspace=request.workspace,
            prompt=request.prompt,
            condition=None,
            sandbox="read-only",
            model=self.judge_model,
            output_schema=request.output_schema,
            include_peers=False,
        )

    def grade_pair(
        self,
        *,
        grade_dir: Path,
        behavior_case: BehaviorCase,
        repeat: int,
        runs_by_condition: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        condition_ids = tuple(condition.id for condition in self.conditions)
        if set(runs_by_condition) != set(condition_ids):
            raise EvalError("grading runs must match the configured conditions")
        evidence_by_condition = {
            condition_id: (
                dict(run["evidence"])
                if isinstance(run.get("evidence"), Mapping)
                else self._evidence_bundle(run)
            )
            for condition_id, run in runs_by_condition.items()
        }
        return grade_behavior(
            self,
            conditions=self.conditions,
            grade_dir=grade_dir,
            behavior_case=behavior_case,
            repeat=repeat,
            evidence_by_condition=evidence_by_condition,
        )
