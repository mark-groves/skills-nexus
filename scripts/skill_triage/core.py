"""Deterministic redaction and private triage storage."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from skill_observation import ObservationError, safe_path_segment

REDACTION_RULES_VERSION = 1
_PLACEHOLDER = {
    "private_key": "[REDACTED:PRIVATE_KEY]",
    "jwt": "[REDACTED:JWT]",
    "aws_access_key": "[REDACTED:AWS_ACCESS_KEY]",
    "github_token": "[REDACTED:GITHUB_TOKEN]",
    "slack_token": "[REDACTED:SLACK_TOKEN]",
    "api_key": "[REDACTED:API_KEY]",
    "bearer": "[REDACTED:BEARER]",
    "labeled_secret": r"\1[REDACTED:SECRET]",
    "email": "[REDACTED:EMAIL]",
    "ssn": "[REDACTED:SSN]",
    "phone": "[REDACTED:PHONE]",
    "home_path": "[REDACTED:HOME_PATH]",
}
_SIGNAL_TEXT_KEYS = (
    "observation",
    "instruction_ref",
    "evidence_excerpt",
    "diagnosis",
)
REDACTION_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN [A-Z ]{0,40}PRIVATE KEY-----.*?-----END [A-Z ]{0,40}PRIVATE KEY-----",
            re.DOTALL,
        ),
        _PLACEHOLDER["private_key"],
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        _PLACEHOLDER["jwt"],
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        _PLACEHOLDER["aws_access_key"],
    ),
    (
        "github_token",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"
        ),
        _PLACEHOLDER["github_token"],
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        _PLACEHOLDER["slack_token"],
    ),
    (
        "api_key",
        re.compile(
            r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b"
            r"|\bAIza[0-9A-Za-z_-]{35}\b"
            r"|\bnpm_[A-Za-z0-9]{36}\b"
            r"|\bglpat-[A-Za-z0-9_-]{20,}\b"
        ),
        _PLACEHOLDER["api_key"],
    ),
    (
        "bearer",
        re.compile(r"(?i)\bBearer\s+(?!\[REDACTED:)\S+"),
        _PLACEHOLDER["bearer"],
    ),
    (
        "labeled_secret",
        re.compile(
            r"(?i)\b((?:password|passwd|api[_-]?key|secret|token|authorization)\s*[:=]\s*)"
            r"(?!\[REDACTED:)\S+"
        ),
        _PLACEHOLDER["labeled_secret"],
    ),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        _PLACEHOLDER["email"],
    ),
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        _PLACEHOLDER["ssn"],
    ),
    (
        "phone",
        re.compile(
            r"\+\d{8,15}\b"
            r"|(?:(?:\+1[-.\s]+)?(?:\(\d{3}\)[-.\s]*|\d{3}[-.\s]+)\d{3}[-.\s]+\d{4}\b)"
        ),
        _PLACEHOLDER["phone"],
    ),
    (
        "home_path",
        re.compile(
            r"(?:/home|/Users|/mnt/c/Users|[A-Za-z]:/Users)/[^/\s]+"
            r"|[A-Za-z]:\\Users\\[^\\\s]+",
            re.IGNORECASE,
        ),
        _PLACEHOLDER["home_path"],
    ),
)


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    result = text
    for name, pattern, replacement in REDACTION_RULES:
        result, matched = pattern.subn(replacement, result)
        if matched:
            counts[name] = matched
    return result, counts


def _redact_optional(value: object, counts: dict[str, int]) -> object:
    if not isinstance(value, str):
        return value
    redacted, increment = redact_text(value)
    for name, matched in increment.items():
        counts[name] = counts.get(name, 0) + matched
    return redacted


def redact_observation(observation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    redacted = copy.deepcopy(observation)
    counts: dict[str, int] = {}
    source = redacted["source"]
    source["external_run_id"] = _redact_optional(source.get("external_run_id"), counts)
    task = redacted["task"]
    task["summary"] = _redact_optional(task["summary"], counts)
    redacted["suggested_change"] = _redact_optional(redacted.get("suggested_change"), counts)
    for signal in redacted["signals"]:
        for key in _SIGNAL_TEXT_KEYS:
            signal[key] = _redact_optional(signal.get(key), counts)
    return redacted, counts


def _reject_symlinks(path: Path, label: str) -> None:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        if component.is_symlink():
            raise ObservationError(f"{label} may not contain symlinks: {component}")


def write_private_json(payload: dict[str, Any], destination: Path) -> Path:
    _reject_symlinks(destination, "triage destination")
    destination_dir = destination.parent
    destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination_dir.is_symlink():
        raise ObservationError(f"triage destination may not be a symlink: {destination_dir}")
    destination_dir.chmod(0o700)
    if destination.is_symlink():
        raise ObservationError(f"triage destination may not be a symlink: {destination}")
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    if destination.exists() and destination.read_bytes() == encoded:
        return destination

    temporary = destination.with_name(f".{destination.name}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    destination.chmod(0o600)
    return destination


def write_redacted_observation(observation: dict[str, Any], output_root: Path) -> Path:
    skill = observation.get("skill")
    skill_id = skill.get("id") if isinstance(skill, dict) else None
    skill_id = safe_path_segment(skill_id, "redacted observation skill.id", maximum=200)
    observation_id = safe_path_segment(
        observation.get("observation_id"),
        "redacted observation observation_id",
        maximum=200,
    )
    return write_private_json(observation, output_root / skill_id / f"{observation_id}.json")
