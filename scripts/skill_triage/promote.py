"""Promote accepted observations into evals.json regression cases."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from skill_eval import EvalError, load_eval_spec
from skill_observation import ObservationError
from skill_review import load_case_groups

UNPROMOTABLE_CLASSIFICATIONS = {"deployment", "environment"}
_TRIGGER_INPUT_KEYS = {"query", "should_trigger"}
_BEHAVIOR_INPUT_KEYS = {"prompt", "expected_behavior", "fixtures", "checks"}


def next_case_id(cases: list[dict[str, Any]]) -> int:
    numeric: list[int] = []
    taken = {str(item.get("id", "")).strip() for item in cases}
    for item in cases:
        raw = item.get("id")
        if isinstance(raw, bool):
            continue
        if isinstance(raw, int):
            numeric.append(raw)
        elif isinstance(raw, str) and raw.strip().isdigit():
            numeric.append(int(raw.strip()))
    candidate = max(numeric) + 1 if numeric else 1
    while str(candidate) in taken:
        candidate += 1
    return candidate


def _json_identity(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _require_keys(payload: dict[str, Any], required: set[str], label: str) -> None:
    if set(payload) != required:
        raise ObservationError(f"{label} must have keys: " + ", ".join(sorted(required)))


def _list_field(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ObservationError(f"{key} must be a list")
    return list(value)


def _existing_id(cases: list[dict[str, Any]], identity: str) -> str | None:
    for case in cases:
        if not isinstance(case, dict):
            continue
        if _json_identity({key: case.get(key) for key in case if key != "id"}) == identity:
            case_id = case.get("id")
            if isinstance(case_id, bool) or not isinstance(case_id, (str, int)):
                continue
            result = str(case_id).strip()
            if result:
                return result
    return None


def append_eval_cases(
    payload: dict[str, Any],
    *,
    trigger: dict[str, Any] | None = None,
    behavior: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str], list[str], list[str], list[str]]:
    updated = copy.deepcopy(payload)
    trigger_evals = _list_field(updated, "trigger_evals")
    behavior_evals = _list_field(updated, "behavior_evals")
    trigger_ids: list[str] = []
    behavior_ids: list[str] = []
    new_trigger_ids: list[str] = []
    new_behavior_ids: list[str] = []
    if trigger is not None:
        _require_keys(trigger, _TRIGGER_INPUT_KEYS, "promoted trigger case")
        existing = _existing_id(trigger_evals, _json_identity(trigger))
        if existing is not None:
            trigger_ids.append(existing)
        else:
            case_id = next_case_id(trigger_evals)
            trigger_evals.append(
                {
                    "id": case_id,
                    "query": trigger["query"],
                    "should_trigger": trigger["should_trigger"],
                }
            )
            trigger_ids.append(str(case_id))
            new_trigger_ids.append(str(case_id))
    if behavior is not None:
        _require_keys(behavior, _BEHAVIOR_INPUT_KEYS, "promoted behavior case")
        existing = _existing_id(behavior_evals, _json_identity(behavior))
        if existing is not None:
            behavior_ids.append(existing)
        else:
            case_id = next_case_id(behavior_evals)
            behavior_evals.append(
                {
                    "id": case_id,
                    "prompt": behavior["prompt"],
                    "expected_behavior": behavior["expected_behavior"],
                    "fixtures": list(behavior["fixtures"]),
                    "checks": list(behavior["checks"]),
                }
            )
            behavior_ids.append(str(case_id))
            new_behavior_ids.append(str(case_id))
    if not trigger_ids and not behavior_ids:
        raise ObservationError("promotion requires a trigger case, a behavior case, or both")
    updated["trigger_evals"] = trigger_evals
    updated["behavior_evals"] = behavior_evals
    return updated, trigger_ids, behavior_ids, new_trigger_ids, new_behavior_ids


def append_case_group_ids(
    payload: dict[str, Any],
    *,
    group_id: str,
    trigger_ids: list[str],
    behavior_ids: list[str],
) -> dict[str, Any]:
    updated = copy.deepcopy(payload)
    groups = updated.get("groups")
    if not isinstance(groups, list):
        raise ObservationError("case groups file must contain a groups list")
    assigned_trigger: set[str] = set()
    assigned_behavior: set[str] = set()
    target: dict[str, Any] | None = None
    for group in groups:
        if not isinstance(group, dict):
            continue
        assigned_trigger.update(str(item).strip() for item in (group.get("trigger_cases") or []))
        assigned_behavior.update(str(item).strip() for item in (group.get("behavior_cases") or []))
        if group.get("id") == group_id:
            target = group
    if target is None:
        raise ObservationError(f"case group {group_id!r} was not found")
    new_trigger = [case_id for case_id in trigger_ids if case_id not in assigned_trigger]
    new_behavior = [case_id for case_id in behavior_ids if case_id not in assigned_behavior]
    if new_trigger or new_behavior:
        target["trigger_cases"] = list(target.get("trigger_cases") or []) + new_trigger
        target["behavior_cases"] = list(target.get("behavior_cases") or []) + new_behavior
    return updated


def _write_repo_json(payload: dict[str, Any], destination: Path) -> None:
    encoded = (json.dumps(payload, indent=2) + "\n").encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(temporary, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _require_fixtures_resolve(eval_dir: Path, payload: dict[str, Any]) -> None:
    behavior_evals = _list_field(payload, "behavior_evals")
    for index, item in enumerate(behavior_evals, start=1):
        if not isinstance(item, dict):
            raise ObservationError(f"behavior_evals[{index}] must be an object")
        fixtures = item.get("fixtures", [])
        if not isinstance(fixtures, list):
            raise ObservationError(f"behavior_evals[{index}].fixtures must be a list")
        for fixture in fixtures:
            if not isinstance(fixture, str) or not fixture.strip():
                raise ObservationError(
                    f"behavior_evals[{index}].fixtures must contain non-empty strings"
                )
            fixture_path = Path(fixture)
            if (
                fixture_path.is_absolute()
                or ".." in fixture_path.parts
                or not fixture_path.parts
                or fixture_path.parts[0] == "evals.json"
                or fixture_path.parts == ("fixtures",)
            ):
                raise ObservationError(
                    "behavior eval fixture paths must be eval-relative, may not traverse "
                    f"parents, and may not select eval ground truth or the broad fixture "
                    f"root: {fixture}"
                )
            candidates = [eval_dir / fixture_path]
            if len(fixture_path.parts) == 1:
                candidates.extend(
                    [
                        eval_dir / "fixtures" / fixture_path,
                        eval_dir / f"{fixture_path}.md",
                    ]
                )
            if not any(candidate.exists() for candidate in candidates):
                raise ObservationError(f"behavior eval fixture is unresolved: {fixture}")


def validate_promoted_suite(
    payload: dict[str, Any],
    *,
    skill_id: str,
    source_eval_dir: Path,
    case_groups: dict[str, Any] | None,
) -> None:
    _require_fixtures_resolve(source_eval_dir, payload)
    with tempfile.TemporaryDirectory() as temp_dir:
        evals_root = Path(temp_dir)
        eval_path = evals_root / skill_id / "evals.json"
        eval_path.parent.mkdir(parents=True)
        eval_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        spec = load_eval_spec(Path(skill_id), evals_root)
        if case_groups is not None:
            groups_path = evals_root / skill_id / "capability-case-groups.json"
            groups_path.write_text(json.dumps(case_groups, indent=2) + "\n", encoding="utf-8")
            load_case_groups(groups_path, spec)


def promote_into_eval_suite(
    *,
    skill_id: str,
    evals_root: Path,
    trigger: dict[str, Any] | None,
    behavior: dict[str, Any] | None,
    group_id: str,
) -> tuple[Path, list[str], list[str], Path | None]:
    eval_path = evals_root / skill_id / "evals.json"
    if not eval_path.is_file():
        raise ObservationError(f"missing eval suite: {eval_path}")
    try:
        payload = json.loads(eval_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"could not read eval suite: {exc}") from exc
    if not isinstance(payload, dict):
        raise ObservationError("eval suite must be an object")
    if payload.get("skill_name") != skill_id:
        raise ObservationError(
            f"eval suite skill_name must be {skill_id!r}, found {payload.get('skill_name')!r}"
        )
    updated, trigger_ids, behavior_ids, new_trigger_ids, new_behavior_ids = append_eval_cases(
        payload, trigger=trigger, behavior=behavior
    )
    groups_path = evals_root / skill_id / "capability-case-groups.json"
    updated_groups: dict[str, Any] | None = None
    if groups_path.is_file():
        try:
            groups_payload = json.loads(groups_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ObservationError(f"could not read case groups: {exc}") from exc
        if not isinstance(groups_payload, dict):
            raise ObservationError("case groups file must be an object")
        updated_groups = append_case_group_ids(
            groups_payload,
            group_id=group_id,
            trigger_ids=trigger_ids,
            behavior_ids=behavior_ids,
        )
    try:
        validate_promoted_suite(
            updated,
            skill_id=skill_id,
            source_eval_dir=eval_path.parent,
            case_groups=updated_groups,
        )
    except EvalError as exc:
        raise ObservationError(f"promoted eval suite is invalid: {exc}") from exc
    if new_trigger_ids or new_behavior_ids:
        _write_repo_json(updated, eval_path)
        if updated_groups is not None:
            _write_repo_json(updated_groups, groups_path)
    if updated_groups is not None:
        return eval_path, trigger_ids, behavior_ids, groups_path
    return eval_path, trigger_ids, behavior_ids, None
