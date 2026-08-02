"""Condition-blind evidence grading shared by every judge harness."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .core import BehaviorCase, EvalError, EvaluationCondition, json_dump
from .engine import materialize_unavailable
from .harness import JudgeHarness, JudgmentRequest


def judgment_schema(labels: tuple[str, ...] = ("A", "B")) -> dict[str, Any]:
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
            "label": {"type": "string", "enum": list(labels)},
            "checks": {"type": "array", "items": check},
            "summary": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "weaknesses": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["label", "checks", "summary", "strengths", "weaknesses"],
        "additionalProperties": False,
    }
    properties: dict[str, Any] = {
        "candidates": {
            "type": "array",
            "items": candidate,
            "minItems": len(labels),
            "maxItems": len(labels),
        },
    }
    required = ["candidates"]
    if len(labels) == 2:
        properties["comparison"] = {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["A_better", "B_better", "tie", "insufficient"],
                },
                "rationale": {"type": "string"},
                "material_differences": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["verdict", "rationale", "material_differences"],
            "additionalProperties": False,
        }
        required.append("comparison")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _blind_map(
    conditions: tuple[EvaluationCondition, ...], behavior_case: BehaviorCase, repeat: int
) -> dict[str, str]:
    condition_ids = tuple(condition.id for condition in conditions)
    labels = tuple(chr(ord("A") + index) for index in range(len(condition_ids)))
    if len(condition_ids) == 2:
        flip = int(hashlib.sha256(f"{behavior_case.id}:{repeat}".encode()).hexdigest(), 16) % 2
        blinded_ids = tuple(reversed(condition_ids)) if flip else condition_ids
    else:
        blinded_ids = tuple(
            sorted(
                condition_ids,
                key=lambda condition_id: hashlib.sha256(
                    f"{behavior_case.id}:{repeat}:{condition_id}".encode()
                ).digest(),
            )
        )
    return dict(zip(labels, blinded_ids, strict=True))


def _validate_string_list(value: object, *, location: str, errors: list[str]) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{location} must be an array of strings")


def validate_judgment(
    judgment: object,
    *,
    labels: tuple[str, ...],
    check_count: int,
) -> list[str]:
    """Validate the canonical judgment locally, independent of harness support."""

    errors: list[str] = []
    if not isinstance(judgment, dict):
        return ["judgment must be an object"]
    expected_root = {"candidates", "comparison"} if len(labels) == 2 else {"candidates"}
    if set(judgment) != expected_root:
        errors.append("judgment fields must exactly match the canonical schema")
    candidates = judgment.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != len(labels):
        errors.append(f"judgment must contain exactly {len(labels)} candidates")
        candidates = []
    seen_labels: set[str] = set()
    expected_candidate = {"label", "checks", "summary", "strengths", "weaknesses"}
    for candidate_index, candidate in enumerate(candidates):
        location = f"candidates[{candidate_index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{location} must be an object")
            continue
        if set(candidate) != expected_candidate:
            errors.append(f"{location} fields must exactly match the canonical schema")
        label = candidate.get("label")
        if not isinstance(label, str) or label not in labels:
            errors.append(f"{location}.label is invalid")
        elif label in seen_labels:
            errors.append(f"duplicate candidate label {label}")
        else:
            seen_labels.add(label)
        if not isinstance(candidate.get("summary"), str):
            errors.append(f"{location}.summary must be a string")
        _validate_string_list(
            candidate.get("strengths"), location=f"{location}.strengths", errors=errors
        )
        _validate_string_list(
            candidate.get("weaknesses"), location=f"{location}.weaknesses", errors=errors
        )
        checks = candidate.get("checks")
        if not isinstance(checks, list) or len(checks) != check_count:
            errors.append(f"{location}.checks must contain exactly {check_count} checks")
            checks = []
        seen_indices: set[int] = set()
        for check_position, check in enumerate(checks):
            check_location = f"{location}.checks[{check_position}]"
            if not isinstance(check, dict):
                errors.append(f"{check_location} must be an object")
                continue
            if set(check) != {"index", "result", "confidence", "evidence"}:
                errors.append(f"{check_location} fields must exactly match the canonical schema")
            index = check.get("index")
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < check_count
            ):
                errors.append(f"{check_location}.index is invalid")
            elif index in seen_indices:
                errors.append(f"{location} has duplicate check index {index}")
            else:
                seen_indices.add(index)
            if check.get("result") not in {"pass", "fail", "unknown"}:
                errors.append(f"{check_location}.result is invalid")
            confidence = check.get("confidence")
            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not 0 <= confidence <= 1
            ):
                errors.append(f"{check_location}.confidence is invalid")
            if not isinstance(check.get("evidence"), str):
                errors.append(f"{check_location}.evidence must be a string")
    if seen_labels != set(labels):
        errors.append("candidate labels must exactly match the blinded labels")
    if len(labels) == 2:
        comparison = judgment.get("comparison")
        if not isinstance(comparison, dict):
            errors.append("comparison must be an object")
        else:
            if set(comparison) != {"verdict", "rationale", "material_differences"}:
                errors.append("comparison fields must exactly match the canonical schema")
            if comparison.get("verdict") not in {
                "A_better",
                "B_better",
                "tie",
                "insufficient",
            }:
                errors.append("comparison.verdict is invalid")
            if not isinstance(comparison.get("rationale"), str):
                errors.append("comparison.rationale must be a string")
            _validate_string_list(
                comparison.get("material_differences"),
                location="comparison.material_differences",
                errors=errors,
            )
    return errors


def grade_behavior(
    judge: JudgeHarness,
    *,
    conditions: tuple[EvaluationCondition, ...],
    grade_dir: Path,
    behavior_case: BehaviorCase,
    repeat: int,
    evidence_by_condition: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    condition_ids = tuple(condition.id for condition in conditions)
    if set(evidence_by_condition) != set(condition_ids):
        raise EvalError("grading evidence must match the configured conditions")
    grade_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(tempfile.mkdtemp(prefix="skill-eval-judge-workspace-"))
    workspace = workspace_root / "workspace"
    workspace.mkdir()
    blind_map = _blind_map(conditions, behavior_case, repeat)
    labels = tuple(blind_map)
    candidates = {
        label: dict(evidence_by_condition[condition_id])
        for label, condition_id in blind_map.items()
    }
    evidence = {
        "task": behavior_case.prompt,
        "expected_behavior": behavior_case.expected_behavior,
        "checks": [
            {"index": index, **check.as_dict()} for index, check in enumerate(behavior_case.checks)
        ],
        "candidates": candidates,
        "grading_policy": {
            "pass": "Concrete transcript or artifact evidence proves the check",
            "fail": "Evidence contradicts the check or proves it was not satisfied",
            "unknown": "Available evidence is insufficient; never assume success",
        },
        "integrity": {
            "condition_identities_withheld": True,
            "labels_randomized": True,
        },
    }
    evidence_path = workspace / "evidence.json"
    schema_path = workspace / "schema.json"
    try:
        json_dump(evidence_path, evidence)
        json_dump(schema_path, judgment_schema(labels))
        label_text = ", ".join(labels)
        prompt = (
            "Act as an evidence-bound, condition-blind evaluator. Read evidence.json. "
            f"Grade candidates {label_text} independently against every numbered check, using "
            "the same standard. Do not reward verbosity, claims of skill use, or plausible "
            "intent. A check passes only when the supplied transcript, Git state, or artifact "
            "evidence proves it. Use unknown when evidence is insufficient. "
            + (
                "Then compare material task quality. "
                if len(labels) == 2
                else "Do not infer or name the hidden evaluation conditions. "
            )
            + "Return only the required structured result."
        )
        raw_executed = judge.execute_judgment(
            JudgmentRequest(
                run_dir=grade_dir,
                workspace=workspace,
                prompt=prompt,
                output_schema=schema_path,
            )
        )
        if not isinstance(raw_executed, Mapping):
            raise EvalError("judge harness returned a non-object result")
        materialized, unavailable_reasons = materialize_unavailable(raw_executed)
        if not isinstance(materialized, dict):
            raise EvalError("judge harness returned a non-object result")
        executed = materialized
        if unavailable_reasons:
            executed["unavailable_evidence"] = unavailable_reasons
    finally:
        shutil.rmtree(workspace_root, ignore_errors=True)

    judgment: dict[str, Any] | None = None
    parse_error: str | None = None
    validation_errors: list[str] = []
    if executed.get("status") == "completed":
        try:
            parsed = json.loads(str(executed.get("final_response", "")))
            if not isinstance(parsed, dict):
                raise ValueError("judgment was not an object")
            judgment = parsed
        except (json.JSONDecodeError, ValueError) as exc:
            parse_error = str(exc)
        if judgment is not None:
            validation_errors = validate_judgment(
                judgment,
                labels=labels,
                check_count=len(behavior_case.checks),
            )

    mapped_grades: dict[str, list[dict[str, Any]]] = {condition.id: [] for condition in conditions}
    if judgment is not None and not validation_errors:
        by_label = {item["label"]: item for item in judgment["candidates"]}
        for label, condition_id in blind_map.items():
            indexed = {item["index"]: item for item in by_label[label]["checks"]}
            for index, check in enumerate(behavior_case.checks):
                item = indexed[index]
                outcome = item["result"]
                mapped_grades[condition_id].append(
                    {
                        "index": index,
                        "check_id": check.id,
                        "check": check.text,
                        "class": check.check_class,
                        "gate": check.gate,
                        "passed": (
                            True if outcome == "pass" else False if outcome == "fail" else None
                        ),
                        "confidence": item["confidence"],
                        "evidence": item["evidence"],
                    }
                )

    status = (
        "completed"
        if executed.get("status") == "completed" and judgment is not None and not validation_errors
        else "invalid"
        if executed.get("status") == "completed"
        else str(executed.get("status", "invalid"))
    )
    result = {
        "status": status,
        "blind_map": blind_map,
        "grades": mapped_grades,
        "judgment": judgment,
        "comparison": judgment.get("comparison") if judgment else None,
        "parse_error": parse_error,
        "validation_errors": validation_errors,
        "duration_seconds": executed.get("duration_seconds"),
        "usage": executed.get("usage"),
        "events_path": executed.get("events_path"),
        "stderr_path": executed.get("stderr_path"),
    }
    if executed.get("unavailable_evidence"):
        result["unavailable_evidence"] = executed["unavailable_evidence"]
    json_dump(grade_dir / "grading.json", result)
    return result
