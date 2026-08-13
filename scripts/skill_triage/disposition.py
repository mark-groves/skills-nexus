"""Fingerprint, classify, and store observation triage dispositions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from skill_observation import ObservationError, safe_path_segment
from skill_observation.core import MAX_INPUT_BYTES

from .core import REDACTION_RULES_VERSION, write_private_json

CLASSIFICATIONS = {
    "instruction",
    "trigger",
    "script",
    "reference",
    "deployment",
    "environment",
}
DISPOSITIONS = {"open", "accept", "reject", "insufficient"}
TERMINAL_DISPOSITIONS = {"accept", "reject", "insufficient"}
DISPOSITION_KEYS = {
    "schema_version",
    "observation_id",
    "skill_id",
    "recorded_at",
    "redaction_rules_version",
    "fingerprint",
    "classification",
    "disposition",
    "reason",
}


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


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ObservationError(f"could not inspect {label}: {exc}") from exc
    if size > MAX_INPUT_BYTES:
        raise ObservationError(f"{label} exceeds {MAX_INPUT_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"could not read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ObservationError(f"{label} must be an object")
    return payload


def _nonempty_text(value: object, location: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ObservationError(f"{location} must be a non-empty string")
    result = value.strip()
    if len(result) > maximum:
        raise ObservationError(f"{location} exceeds {maximum} characters")
    return result


def _sha256_hex(value: object, location: str) -> str:
    digest = _nonempty_text(value, location, maximum=64)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ObservationError(f"{location} must be 64 lowercase hex characters")
    return digest


def _normalize_reason(disposition: str, reason: object) -> str | None:
    if disposition == "open":
        if reason is not None:
            raise ObservationError("open disposition reason must be null")
        return None
    if not isinstance(reason, str) or not reason.strip():
        raise ObservationError(f"{disposition} disposition reason must be a non-empty string")
    stripped = reason.strip()
    if len(stripped) > 2000:
        raise ObservationError("reason exceeds 2000 characters")
    return stripped


def _normalize_disposition(payload: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(payload, DISPOSITION_KEYS, "disposition")
    if payload["schema_version"] != 1:
        raise ObservationError("schema_version must be 1")
    if payload["redaction_rules_version"] != REDACTION_RULES_VERSION:
        raise ObservationError(f"redaction_rules_version must be {REDACTION_RULES_VERSION}")
    classification = payload["classification"]
    if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
        raise ObservationError(
            f"classification must be one of: {', '.join(sorted(CLASSIFICATIONS))}"
        )
    disposition = payload["disposition"]
    if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
        raise ObservationError(f"disposition must be one of: {', '.join(sorted(DISPOSITIONS))}")
    return {
        "schema_version": 1,
        "observation_id": safe_path_segment(
            payload["observation_id"], "observation_id", maximum=200
        ),
        "skill_id": safe_path_segment(payload["skill_id"], "skill_id", maximum=200),
        "recorded_at": _nonempty_text(payload["recorded_at"], "recorded_at", maximum=100),
        "redaction_rules_version": REDACTION_RULES_VERSION,
        "fingerprint": _sha256_hex(payload["fingerprint"], "fingerprint"),
        "classification": classification,
        "disposition": disposition,
        "reason": _normalize_reason(disposition, payload["reason"]),
    }


def fingerprint_observation(observation: dict[str, Any]) -> str:
    payload = {
        "redaction_rules_version": REDACTION_RULES_VERSION,
        "skill_id": observation["skill"]["id"],
        "signals": [
            {
                "kind": signal["kind"],
                "instruction_ref": signal["instruction_ref"],
                "observation": signal["observation"],
                "diagnosis": signal["diagnosis"],
            }
            for signal in observation["signals"]
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def disposition_path(output_root: Path, skill_id: str, observation_id: str) -> Path:
    return output_root / skill_id / f"{observation_id}.disposition.json"


def load_disposition(path: Path) -> dict[str, Any]:
    return _normalize_disposition(_read_json_object(path, "disposition"))


def iter_dispositions(skill_dir: Path) -> list[dict[str, Any]]:
    if not skill_dir.is_dir():
        return []
    return [load_disposition(path) for path in sorted(skill_dir.glob("*.disposition.json"))]


def cluster_for(fingerprint: str, dispositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [item for item in dispositions if item["fingerprint"] == fingerprint],
        key=lambda item: (item["recorded_at"], item["observation_id"]),
    )


def build_disposition(
    observation: dict[str, Any],
    *,
    classification: str,
    disposition: str = "open",
    reason: str | None = None,
) -> dict[str, Any]:
    return _normalize_disposition(
        {
            "schema_version": 1,
            "observation_id": observation["observation_id"],
            "skill_id": observation["skill"]["id"],
            "recorded_at": observation["recorded_at"],
            "redaction_rules_version": REDACTION_RULES_VERSION,
            "fingerprint": fingerprint_observation(observation),
            "classification": classification,
            "disposition": disposition,
            "reason": reason,
        }
    )


def write_disposition(record: dict[str, Any], output_root: Path) -> Path:
    normalized = _normalize_disposition(record)
    destination = disposition_path(
        output_root, normalized["skill_id"], normalized["observation_id"]
    )
    if destination.exists():
        existing = load_disposition(destination)
        if existing["disposition"] != "open":
            raise ObservationError(
                f"observation {normalized['observation_id']} already has disposition "
                f"{existing['disposition']}"
            )
    return write_private_json(normalized, destination)


def load_optional_disposition(
    output_root: Path, skill_id: str, observation_id: str
) -> dict[str, Any] | None:
    destination = disposition_path(output_root, skill_id, observation_id)
    if not destination.exists():
        return None
    return load_disposition(destination)


def refuse_closed_disposition(output_root: Path, skill_id: str, observation_id: str) -> None:
    record = load_optional_disposition(output_root, skill_id, observation_id)
    if record is not None and record["disposition"] != "open":
        raise ObservationError(
            f"observation {observation_id} already has disposition {record['disposition']}"
        )


def require_open_disposition(
    output_root: Path,
    observation: dict[str, Any],
) -> dict[str, Any]:
    skill = observation.get("skill")
    skill_id = skill.get("id") if isinstance(skill, dict) else None
    observation_id = observation.get("observation_id")
    if not isinstance(skill_id, str) or not isinstance(observation_id, str):
        raise ObservationError("observation must include skill.id and observation_id")
    record = load_optional_disposition(output_root, skill_id, observation_id)
    if record is None:
        raise ObservationError(
            f"observation {observation_id} has no open disposition; classify it first"
        )
    if record["disposition"] != "open":
        raise ObservationError(
            f"observation {observation_id} already has disposition {record['disposition']}"
        )
    expected_fingerprint = fingerprint_observation(observation)
    if record["fingerprint"] != expected_fingerprint:
        raise ObservationError(
            f"observation {observation_id} disposition fingerprint does not match "
            "the current observation; reclassify it first"
        )
    recorded_at = observation.get("recorded_at")
    if record["recorded_at"] != recorded_at:
        raise ObservationError(
            f"observation {observation_id} disposition recorded_at does not match "
            "the current observation; reclassify it first"
        )
    return record


def close_disposition(
    record: dict[str, Any],
    *,
    disposition: str,
    reason: str,
) -> dict[str, Any]:
    if disposition not in TERMINAL_DISPOSITIONS:
        raise ObservationError(
            "close disposition must be one of: " + ", ".join(sorted(TERMINAL_DISPOSITIONS))
        )
    if record.get("disposition") != "open":
        raise ObservationError(
            f"observation {record.get('observation_id')} already has disposition "
            f"{record.get('disposition')}"
        )
    return _normalize_disposition({**record, "disposition": disposition, "reason": reason})
