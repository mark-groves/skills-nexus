"""Harness-neutral evidence normalization and redaction."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def _all_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_strings(nested)


def _scrub(value: str, replacements: dict[str, str]) -> str:
    result = value
    for original, replacement in sorted(
        replacements.items(), key=lambda item: len(item[0]), reverse=True
    ):
        result = result.replace(original, replacement)
    return result


def _redact_skill_paths(value: str, markers: set[str]) -> str:
    """Replace full path tokens that identify installed skill instructions."""

    result = value.replace("\\", "/")
    delimiters = set(" \t\r\n\"'`=;|&()<>")
    for marker in sorted(markers, key=len, reverse=True):
        while marker in result:
            marker_start = result.index(marker)
            token_start = marker_start
            while token_start and result[token_start - 1] not in delimiters:
                token_start -= 1
            marker_end = marker_start + len(marker)
            result = result[:token_start] + "<SKILL_INSTRUCTIONS>" + result[marker_end:]
    return result


def _may_expose_skill_instructions(
    command: str,
    output: str,
    activation_markers: set[str],
    runtime_home: str,
) -> bool:
    """Detect direct and shell-expanded reads from an installed skill tree."""

    normalized_command = command.replace("\\", "/")
    normalized_output = output.replace("\\", "/")
    combined = f"{normalized_command}\n{normalized_output}"
    if any(marker in combined for marker in activation_markers):
        return True

    if not runtime_home or runtime_home not in combined:
        return False

    lowered_command = normalized_command.lower()
    normalized_home = runtime_home.replace("\\", "/")
    if "skill.md" in lowered_command or f"{normalized_home}/.agents/skills" in combined:
        return True

    return bool(
        re.search(
            r"\b(?:awk|cat|find|grep|head|less|more|perl|python\d*|rg|ruby|sed|tail|xargs)\b",
            lowered_command,
        )
    )


def _contains_instruction_excerpt(text: str, instructions: tuple[str, ...]) -> bool:
    for instruction_text in instructions:
        if instruction_text in text or (len(text) >= 80 and text in instruction_text):
            return True
        if any(
            len(line.strip()) >= 40 and line.strip() in text
            for line in instruction_text.splitlines()
        ):
            return True
    return False


def _redact_artifact_instructions(
    artifact_delta: dict[str, Any], instructions: tuple[str, ...]
) -> dict[str, Any]:
    redacted = copy.deepcopy(artifact_delta)
    for change_type in ("created", "modified", "deleted"):
        for record in redacted.get(change_type, []):
            text = record.get("text")
            if isinstance(text, str) and _contains_instruction_excerpt(text, instructions):
                record["text"] = "<REDACTED: artifact included skill instructions>"
                record["text_redacted"] = True
    return redacted


def build_evidence_bundle(
    run: Mapping[str, Any],
    *,
    commands: Iterable[Mapping[str, Any]],
    runtime_skill_names: set[str],
    runtime_instruction_texts: tuple[str, ...],
    runtime_home_label: str = "<HARNESS_HOME>",
) -> dict[str, Any]:
    """Build bounded judge evidence from an adapter-normalized task run."""

    workspace = str(Path(str(run["workspace"])).resolve())
    execution_workspace = str(Path(str(run.get("execution_workspace", run["workspace"]))).resolve())
    run_root = str(Path(execution_workspace).parent.resolve())
    runtime_home = str(run.get("runtime_home", "")).replace("\\", "/")
    replacements = {
        workspace: "<WORKSPACE>",
        execution_workspace: "<WORKSPACE>",
        run_root: "<RUN_ROOT>",
    }
    if runtime_home:
        replacements[runtime_home] = runtime_home_label
    activation_markers = {
        f"{runtime_home}/.agents/skills/{name}/SKILL.md"
        for name in runtime_skill_names
        if runtime_home
    }
    normalized_commands: list[dict[str, Any]] = []
    for item in commands:
        command = str(item.get("command", ""))
        scrubbed_command = _redact_skill_paths(command, activation_markers)
        raw_output = str(item.get("output", ""))[-5000:]
        command_includes_instructions = _contains_instruction_excerpt(
            command, runtime_instruction_texts
        )
        read_skill = _may_expose_skill_instructions(
            command, raw_output, activation_markers, runtime_home
        ) or _contains_instruction_excerpt(raw_output, runtime_instruction_texts)
        normalized_commands.append(
            {
                "command": (
                    "<REDACTED: command included skill instructions>"
                    if command_includes_instructions
                    else _scrub(scrubbed_command, replacements)
                ),
                "exit_code": item.get("exit_code"),
                "status": item.get("status"),
                "output": (
                    "<REDACTED: command output included skill instructions>"
                    if read_skill
                    else _scrub(raw_output, replacements)
                ),
            }
        )
    final = _scrub(str(run.get("final_response", "")), replacements)
    if _contains_instruction_excerpt(final, runtime_instruction_texts):
        final = "<REDACTED: final response included skill instructions>"
    artifact_delta = run.get("artifact_delta")
    if not isinstance(artifact_delta, dict):
        artifact_delta = {"created": [], "modified": [], "deleted": []}
    bundle = {
        "status": run.get("status", "invalid"),
        "final_response": final[-20_000:],
        "commands": normalized_commands[-40:],
        "artifact_delta": _redact_artifact_instructions(
            artifact_delta,
            runtime_instruction_texts,
        ),
        "git": run.get("git", {"available": False}),
        "duration_seconds": run.get("duration_seconds"),
        "usage": run.get("usage"),
        "tool_calls": run.get("tool_calls"),
    }
    if run.get("unavailable_evidence"):
        bundle["unavailable_evidence"] = run["unavailable_evidence"]
    return bundle
