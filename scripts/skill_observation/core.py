"""Validation and storage for versioned skill observations."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skill_eval.core import stable_digest

MAX_INPUT_BYTES = 64 * 1024
MAX_SIGNALS = 20
OUTCOMES = {"success", "partial", "failure", "unknown"}
SOURCE_KINDS = {"agent", "human", "harness", "eval"}
INVOCATIONS = {"automatic", "explicit", "unknown"}
ACTIVATIONS = {"activated", "not_activated", "unknown"}
SIGNAL_KINDS = {
    "worked",
    "obstacle",
    "instruction_confusion",
    "instruction_gap",
    "instruction_conflict",
    "workaround",
    "unexpected_behavior",
    "other",
}
CONFIDENCE = {"low", "medium", "high"}


class ObservationError(ValueError):
    """Raised when an observation draft or destination violates the contract."""


def _exact_keys(value: dict[str, Any], expected: set[str], location: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unexpected {', '.join(extra)}")
        raise ObservationError(f"{location} has invalid fields: {'; '.join(details)}")


def _object(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObservationError(f"{location} must be an object")
    return value


def _text(
    value: object,
    location: str,
    *,
    maximum: int,
    nullable: bool = False,
) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ObservationError(f"{location} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise ObservationError(f"{location} exceeds {maximum} characters")
    if any(ord(char) < 32 and char not in "\n\t" for char in result):
        raise ObservationError(f"{location} contains control characters")
    return result


def _enum(value: object, allowed: set[str], location: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ObservationError(f"{location} must be one of: {', '.join(sorted(allowed))}")
    return value


def _optional_enum(value: object, allowed: set[str], location: str) -> str | None:
    if value is None:
        return None
    return _enum(value, allowed, location)


def load_draft(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ObservationError(f"could not inspect observation draft: {exc}") from exc
    if size > MAX_INPUT_BYTES:
        raise ObservationError(f"observation draft exceeds {MAX_INPUT_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"could not read observation draft: {exc}") from exc

    draft = _object(payload, "draft")
    _exact_keys(
        draft,
        {
            "schema_version",
            "source",
            "runtime",
            "task",
            "outcome",
            "signals",
            "suggested_change",
        },
        "draft",
    )
    if draft["schema_version"] != 1:
        raise ObservationError("schema_version must be 1")

    source = _object(draft["source"], "source")
    _exact_keys(source, {"kind", "external_run_id"}, "source")
    normalized_source = {
        "kind": _enum(source["kind"], SOURCE_KINDS, "source.kind"),
        "external_run_id": _text(
            source["external_run_id"], "source.external_run_id", maximum=200, nullable=True
        ),
    }

    runtime = _object(draft["runtime"], "runtime")
    _exact_keys(
        runtime,
        {"harness", "harness_version", "model", "invocation", "activation"},
        "runtime",
    )
    normalized_runtime = {
        "harness": _text(runtime["harness"], "runtime.harness", maximum=100),
        "harness_version": _text(
            runtime["harness_version"], "runtime.harness_version", maximum=100, nullable=True
        ),
        "model": _text(runtime["model"], "runtime.model", maximum=200, nullable=True),
        "invocation": _enum(runtime["invocation"], INVOCATIONS, "runtime.invocation"),
        "activation": _enum(runtime["activation"], ACTIVATIONS, "runtime.activation"),
    }

    task = _object(draft["task"], "task")
    _exact_keys(task, {"category", "summary"}, "task")
    normalized_task = {
        "category": _text(task["category"], "task.category", maximum=100),
        "summary": _text(task["summary"], "task.summary", maximum=1000),
    }

    signals = draft["signals"]
    if not isinstance(signals, list) or not signals:
        raise ObservationError("signals must be a non-empty list")
    if len(signals) > MAX_SIGNALS:
        raise ObservationError(f"signals may contain at most {MAX_SIGNALS} entries")
    normalized_signals: list[dict[str, Any]] = []
    for index, item in enumerate(signals):
        signal = _object(item, f"signals[{index}]")
        _exact_keys(
            signal,
            {
                "kind",
                "observation",
                "instruction_ref",
                "evidence_excerpt",
                "diagnosis",
                "diagnosis_confidence",
            },
            f"signals[{index}]",
        )
        diagnosis = _text(
            signal["diagnosis"],
            f"signals[{index}].diagnosis",
            maximum=1000,
            nullable=True,
        )
        diagnosis_confidence = _optional_enum(
            signal["diagnosis_confidence"],
            CONFIDENCE,
            f"signals[{index}].diagnosis_confidence",
        )
        if (diagnosis is None) != (diagnosis_confidence is None):
            raise ObservationError(
                f"signals[{index}].diagnosis and diagnosis_confidence must both be set or null"
            )
        normalized_signals.append(
            {
                "kind": _enum(signal["kind"], SIGNAL_KINDS, f"signals[{index}].kind"),
                "observation": _text(
                    signal["observation"],
                    f"signals[{index}].observation",
                    maximum=1000,
                ),
                "instruction_ref": _text(
                    signal["instruction_ref"],
                    f"signals[{index}].instruction_ref",
                    maximum=500,
                    nullable=True,
                ),
                "evidence_excerpt": _text(
                    signal["evidence_excerpt"],
                    f"signals[{index}].evidence_excerpt",
                    maximum=2000,
                    nullable=True,
                ),
                "diagnosis": diagnosis,
                "diagnosis_confidence": diagnosis_confidence,
            }
        )

    return {
        "schema_version": 1,
        "source": normalized_source,
        "runtime": normalized_runtime,
        "task": normalized_task,
        "outcome": _enum(draft["outcome"], OUTCOMES, "outcome"),
        "signals": normalized_signals,
        "suggested_change": _text(
            draft["suggested_change"], "suggested_change", maximum=2000, nullable=True
        ),
    }


def _git_value(repo_root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_observation(draft: dict[str, Any], *, skill_dir: Path, repo_root: Path) -> dict[str, Any]:
    skill_dir = skill_dir.resolve()
    repo_root = repo_root.resolve()
    commit = _git_value(repo_root, "rev-parse", "HEAD")
    status = _git_value(repo_root, "status", "--porcelain")
    return {
        "schema_version": draft["schema_version"],
        "observation_id": str(uuid.uuid4()),
        "recorded_at": datetime.now(UTC).isoformat(),
        "trust": "untrusted",
        "source": draft["source"],
        "skill": {
            "id": skill_dir.name,
            "runtime_digest_sha256": stable_digest(skill_dir, exclude={"working", "__pycache__"}),
            "repository_commit": commit,
            "repository_dirty": bool(status) if status is not None else None,
        },
        "runtime": draft["runtime"],
        "task": draft["task"],
        "outcome": draft["outcome"],
        "signals": draft["signals"],
        "suggested_change": draft["suggested_change"],
    }


def write_observation(observation: dict[str, Any], output_root: Path) -> Path:
    absolute_root = output_root.absolute()
    for component in (absolute_root, *absolute_root.parents):
        if component.is_symlink():
            raise ObservationError(f"observation output path may not contain symlinks: {component}")
    skill_name = observation["skill"]["id"]
    destination_dir = output_root / skill_name
    destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination_dir.is_symlink():
        raise ObservationError(f"observation destination may not be a symlink: {destination_dir}")
    destination_dir.chmod(0o700)
    destination = destination_dir / f"{observation['observation_id']}.json"
    payload = (json.dumps(observation, indent=2, sort_keys=True) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination
