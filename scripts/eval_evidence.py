#!/usr/bin/env python3
"""Emit, admit, and summarize Cloud Agent prove artifacts. Does not spawn agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Never, NoReturn

SCHEMA_VERSION = 1
HARNESS = "cursor-cloud-agent"
DEFAULT_MIN_SAMPLE = 2
LEDGER_NAME = "ledger.json"
TASKS_DIR = "tasks"
RETURNS_DIR = "returns"
ADMITTED_DIR = "admitted"

Aggregation = Literal["rank-all", "first-pass", "best-of"]
Kind = Literal["trigger", "behavior"]

MODES = ("prove-variant", "swarm-slice")
AGGREGATIONS: tuple[Aggregation, ...] = ("rank-all", "first-pass", "best-of")
VERDICTS = ("promote", "reject", "inconclusive")
DECLARATIONS = ("PASS", "ISSUES", "BLOCKED")
ROLES = ("current", "baseline", "candidate")
KINDS: tuple[Kind, ...] = ("trigger", "behavior")

LIMIT_NO_NEGATIVE = "no-automatic-negative-activation"
LIMIT_NO_CAPOPT = "no-capopt-non-inferiority-from-chats"
LIMIT_NO_CROSS_HARNESS = "no-cross-harness-claim"
LIMIT_NO_AUTO_PROMOTE = "no-auto-promote"
LIMIT_FIRST_PASS = "first-pass-not-comparative-green"
LIMIT_BEST_OF = "best-of-diagnostic-only"
LIMIT_SAMPLE_SIZE = "sample-size"
LIMIT_MISSING_JUDGE = "missing-judge"
LIMIT_PLATFORM_CAP = "platform-cap"

ALWAYS_HELD = (
    LIMIT_NO_NEGATIVE,
    LIMIT_NO_CAPOPT,
    LIMIT_NO_CROSS_HARNESS,
    LIMIT_NO_AUTO_PROMOTE,
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,31}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
SAFE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
NAME_RE = re.compile(r"^(?!\.\.?$)[^/\\\x00]+$")
VOCAB_RE = re.compile(
    r"\b(?:eval|test|judge|experiment|rubric|score|compare|benchmark|candidate|arena)s?\b",
    re.IGNORECASE,
)

SPEC_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "mode",
        "aggregation",
        "skill_name",
        "git_sha",
        "case",
        "variants",
        "rubric",
        "workers",
        "min_sample",
        "judge_present",
        "platform_cap",
    }
)
REQUIRED_SPEC_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "mode",
        "aggregation",
        "skill_name",
        "git_sha",
        "case",
        "variants",
        "rubric",
        "workers",
    }
)
WORKER_KEYS = frozenset(
    {"label", "model", "variant_id", "goal", "prompt", "install_root", "note_path"}
)
TASK_KEYS = frozenset({"schema_version", "label", "goal", "prompt", "install_root", "note_path"})
RETURN_KEYS = frozenset(
    {
        "label",
        "transcript_ref",
        "declaration",
        "workspace_digest_sha256",
        "changed_file_digests",
    }
)
REQUIRED_RETURN_KEYS = frozenset(
    {"label", "transcript_ref", "declaration", "workspace_digest_sha256"}
)


class EvidenceError(RuntimeError):
    """Raised for a user-actionable emit, admit, or summarize error."""


def _unhandled(value: Never) -> NoReturn:
    raise EvidenceError(f"unhandled value: {value!r}")


def _object(value: object, *, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{location} must be an object")
    return value


def _keys(
    value: dict[str, Any], allowed: frozenset[str], required: frozenset[str], *, location: str
) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - allowed)
    details = []
    if missing:
        details.append("missing " + ", ".join(missing))
    if extra:
        details.append("unexpected " + ", ".join(extra))
    if details:
        raise EvidenceError(f"{location} has invalid keys ({'; '.join(details)})")


def _text(value: object, *, location: str, min_len: int = 1, max_len: int = 400) -> str:
    if not isinstance(value, str) or not min_len <= len(value) <= max_len:
        raise EvidenceError(f"{location} must be a string of length {min_len} to {max_len}")
    return value


def _sha256(value: object, *, location: str) -> str:
    text = _text(value, location=location, min_len=64, max_len=64)
    if not SHA256_RE.fullmatch(text):
        raise EvidenceError(f"{location} must be a lowercase sha256 hex digest")
    return text


def _label(value: object, *, location: str) -> str:
    text = _text(value, location=location, max_len=32)
    if not LABEL_RE.fullmatch(text):
        raise EvidenceError(f"{location} must be a sanitized label")
    return text


def _walk_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        found: list[str] = []
        for key, item in value.items():
            if isinstance(key, str):
                found.append(key)
            found.extend(_walk_strings(item))
        return tuple(found)
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_walk_strings(item))
        return tuple(found)
    return ()


def forbidden_vocab(text: str) -> tuple[str, ...]:
    return tuple(sorted({match.group(0).lower() for match in VOCAB_RE.finditer(text)}))


def refuse_worker_facing(payload: object, *paths: str) -> None:
    scanned = list(_walk_strings(payload))
    scanned.extend(paths)
    hits: list[str] = []
    for item in scanned:
        found = forbidden_vocab(item)
        if found:
            hits.append(f"{item!r} ({', '.join(found)})")
    if hits:
        raise EvidenceError(
            "eval vocabulary in a worker-facing field refuses emit: " + "; ".join(hits)
        )


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceError(f"Missing {label}: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError(f"Unable to read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"Invalid JSON in {label} {path}: {exc}") from exc


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe_under(root: Path, rel: str, *, location: str) -> Path:
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvidenceError(f"{location} must be a relative path without '..'")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise EvidenceError(f"{location} escapes the workspace root")
    return resolved


def _as_kind(value: str) -> Kind:
    if value == "trigger":
        return "trigger"
    if value == "behavior":
        return "behavior"
    raise EvidenceError(f"unknown case kind: {value}")


def _literal(value: object, choices: tuple[str, ...], *, location: str) -> str:
    if value not in choices:
        raise EvidenceError(f"{location} must be one of {', '.join(choices)}")
    return str(value)


def _validate_case(value: object) -> dict[str, Any]:
    case = _object(value, location="case")
    allowed = frozenset(
        {
            "schema_version",
            "skill_name",
            "case_id",
            "kind",
            "query",
            "should_trigger",
            "prompt",
            "expected_behavior",
            "fixtures",
            "evals_json_digest_sha256",
            "fixture_digest_sha256",
        }
    )
    required = frozenset(
        {"schema_version", "skill_name", "case_id", "kind", "evals_json_digest_sha256"}
    )
    _keys(case, allowed, required, location="case")
    if case["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("case.schema_version must be 1")
    skill_name = _text(case["skill_name"], location="case.skill_name", max_len=200)
    if not NAME_RE.fullmatch(skill_name):
        raise EvidenceError("case.skill_name is not a safe skill name")
    case_id = _text(case["case_id"], location="case.case_id", max_len=64)
    if not NAME_RE.fullmatch(case_id):
        raise EvidenceError("case.case_id is not a safe case id")
    kind = _as_kind(_literal(case["kind"], KINDS, location="case.kind"))
    _sha256(case["evals_json_digest_sha256"], location="case.evals_json_digest_sha256")
    if "fixture_digest_sha256" in case:
        _sha256(case["fixture_digest_sha256"], location="case.fixture_digest_sha256")
    if kind == "trigger":
        if "query" not in case or "should_trigger" not in case:
            raise EvidenceError("trigger case requires query and should_trigger")
        _text(case["query"], location="case.query", max_len=4000)
        if not isinstance(case["should_trigger"], bool):
            raise EvidenceError("case.should_trigger must be a boolean")
    elif kind == "behavior":
        if "prompt" not in case or "expected_behavior" not in case:
            raise EvidenceError("behavior case requires prompt and expected_behavior")
        _text(case["prompt"], location="case.prompt", max_len=8000)
        _text(case["expected_behavior"], location="case.expected_behavior", max_len=8000)
    else:
        _unhandled(kind)
    if "fixtures" in case:
        fixtures = case["fixtures"]
        if not isinstance(fixtures, list) or not all(
            isinstance(item, str) and 1 <= len(item) <= 400 for item in fixtures
        ):
            raise EvidenceError("case.fixtures must be a list of paths")
    return case


def _validate_variant(value: object, *, location: str) -> dict[str, Any]:
    variant = _object(value, location=location)
    allowed = frozenset(
        {
            "schema_version",
            "role",
            "logical_skill_name",
            "digest_sha256",
            "plugin_digest_sha256",
            "variant_id",
        }
    )
    required = frozenset(
        {
            "schema_version",
            "role",
            "logical_skill_name",
            "digest_sha256",
            "plugin_digest_sha256",
            "variant_id",
        }
    )
    _keys(variant, allowed, required, location=location)
    if variant["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError(f"{location}.schema_version must be 1")
    _literal(variant["role"], ROLES, location=f"{location}.role")
    name = _text(
        variant["logical_skill_name"], location=f"{location}.logical_skill_name", max_len=200
    )
    if not NAME_RE.fullmatch(name):
        raise EvidenceError(f"{location}.logical_skill_name is not a safe skill name")
    _sha256(variant["digest_sha256"], location=f"{location}.digest_sha256")
    _sha256(variant["plugin_digest_sha256"], location=f"{location}.plugin_digest_sha256")
    variant_id = _text(variant["variant_id"], location=f"{location}.variant_id", max_len=64)
    if not SAFE_ID_RE.fullmatch(variant_id):
        raise EvidenceError(f"{location}.variant_id must be lowercase kebab-case")
    return variant


def _validate_rubric(value: object) -> dict[str, Any]:
    rubric = _object(value, location="rubric")
    _keys(
        rubric,
        frozenset({"schema_version", "criteria"}),
        frozenset({"schema_version", "criteria"}),
        location="rubric",
    )
    if rubric["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("rubric.schema_version must be 1")
    criteria = rubric["criteria"]
    if not isinstance(criteria, list) or not 3 <= len(criteria) <= 6:
        raise EvidenceError("rubric.criteria must contain 3 to 6 items")
    seen: set[str] = set()
    for index, item in enumerate(criteria):
        loc = f"rubric.criteria[{index}]"
        row = _object(item, location=loc)
        _keys(row, frozenset({"id", "text"}), frozenset({"id", "text"}), location=loc)
        criterion_id = _text(row["id"], location=f"{loc}.id", max_len=64)
        if not SAFE_ID_RE.fullmatch(criterion_id):
            raise EvidenceError(f"{loc}.id must be lowercase kebab-case")
        if criterion_id in seen:
            raise EvidenceError(f"duplicate rubric criterion id: {criterion_id}")
        seen.add(criterion_id)
        _text(row["text"], location=f"{loc}.text", max_len=400)
    return rubric


def _validate_worker(value: object, *, location: str, variant_ids: set[str]) -> dict[str, Any]:
    worker = _object(value, location=location)
    _keys(worker, WORKER_KEYS, WORKER_KEYS, location=location)
    label = _label(worker["label"], location=f"{location}.label")
    _text(worker["model"], location=f"{location}.model", max_len=160)
    variant_id = _text(worker["variant_id"], location=f"{location}.variant_id", max_len=64)
    if variant_id not in variant_ids:
        raise EvidenceError(f"{location}.variant_id {variant_id!r} is not in variants")
    _text(worker["goal"], location=f"{location}.goal", max_len=800)
    _text(worker["prompt"], location=f"{location}.prompt", max_len=8000)
    _text(worker["install_root"], location=f"{location}.install_root", max_len=400)
    _text(worker["note_path"], location=f"{location}.note_path", max_len=400)
    refuse_worker_facing(
        {
            "label": label,
            "goal": worker["goal"],
            "prompt": worker["prompt"],
            "install_root": worker["install_root"],
            "note_path": worker["note_path"],
        },
        f"{TASKS_DIR}/{label}.json",
        worker["install_root"],
        worker["note_path"],
    )
    return worker


def validate_spec(value: object) -> dict[str, Any]:
    spec = _object(value, location="spec")
    _keys(spec, SPEC_KEYS, REQUIRED_SPEC_KEYS, location="spec")
    if spec["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("spec.schema_version must be 1")
    _text(spec["run_id"], location="spec.run_id", max_len=64)
    if not SAFE_ID_RE.fullmatch(spec["run_id"]):
        raise EvidenceError("spec.run_id must be lowercase kebab-case")
    _literal(spec["mode"], MODES, location="spec.mode")
    _literal(spec["aggregation"], AGGREGATIONS, location="spec.aggregation")
    skill_name = _text(spec["skill_name"], location="spec.skill_name", max_len=200)
    if not NAME_RE.fullmatch(skill_name):
        raise EvidenceError("spec.skill_name is not a safe skill name")
    git_sha = _text(spec["git_sha"], location="spec.git_sha", max_len=40)
    if not GIT_SHA_RE.fullmatch(git_sha):
        raise EvidenceError("spec.git_sha must be a git sha")
    case = _validate_case(spec["case"])
    if case["skill_name"] != skill_name:
        raise EvidenceError("case.skill_name must match spec.skill_name")
    variants = spec["variants"]
    if not isinstance(variants, list) or not variants:
        raise EvidenceError("spec.variants must be a non-empty list")
    parsed_variants = [
        _validate_variant(item, location=f"spec.variants[{index}]")
        for index, item in enumerate(variants)
    ]
    variant_ids = {item["variant_id"] for item in parsed_variants}
    if len(variant_ids) != len(parsed_variants):
        raise EvidenceError("spec.variants must have unique variant_id values")
    _validate_rubric(spec["rubric"])
    workers = spec["workers"]
    if not isinstance(workers, list) or not workers:
        raise EvidenceError("spec.workers must be a non-empty list")
    labels: set[str] = set()
    for index, item in enumerate(workers):
        worker = _validate_worker(item, location=f"spec.workers[{index}]", variant_ids=variant_ids)
        if worker["label"] in labels:
            raise EvidenceError(f"duplicate worker label: {worker['label']}")
        labels.add(worker["label"])
    if "min_sample" in spec:
        min_sample = spec["min_sample"]
        if not isinstance(min_sample, int) or isinstance(min_sample, bool) or min_sample < 1:
            raise EvidenceError("spec.min_sample must be a positive integer")
    if "judge_present" in spec and not isinstance(spec["judge_present"], bool):
        raise EvidenceError("spec.judge_present must be a boolean")
    if "platform_cap" in spec and not isinstance(spec["platform_cap"], bool):
        raise EvidenceError("spec.platform_cap must be a boolean")
    return spec


def worker_task(worker: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "label": worker["label"],
        "goal": worker["goal"],
        "prompt": worker["prompt"],
        "install_root": worker["install_root"],
        "note_path": worker["note_path"],
    }


def emit(spec: object, run_dir: Path) -> Path:
    validated = validate_spec(spec)
    run_dir = run_dir.resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise EvidenceError(f"run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    for worker in validated["workers"]:
        task = worker_task(worker)
        dest = run_dir / TASKS_DIR / f"{worker['label']}.json"
        refuse_worker_facing(task, dest.name, f"{TASKS_DIR}/{worker['label']}.json")
        _write_json(dest, task)
    _write_json(run_dir / LEDGER_NAME, validated)
    return run_dir / LEDGER_NAME


def load_ledger(run_dir: Path) -> dict[str, Any]:
    return validate_spec(_load_json(run_dir / LEDGER_NAME, label="ledger"))


def _variant_for(ledger: Mapping[str, Any], variant_id: str) -> dict[str, Any]:
    for item in ledger["variants"]:
        if item["variant_id"] == variant_id:
            return item
    raise EvidenceError(f"ledger has no variant {variant_id!r}")


def _worker_for(ledger: Mapping[str, Any], label: str) -> dict[str, Any]:
    for item in ledger["workers"]:
        if item["label"] == label:
            return item
    raise EvidenceError(f"ledger has no worker {label!r}")


def _pins(ledger: Mapping[str, Any], worker: Mapping[str, Any]) -> dict[str, Any]:
    variant = _variant_for(ledger, worker["variant_id"])
    case = ledger["case"]
    pins: dict[str, Any] = {
        "logical_skill_name": variant["logical_skill_name"],
        "skill_digest_sha256": variant["digest_sha256"],
        "plugin_digest_sha256": variant["plugin_digest_sha256"],
        "case_id": case["case_id"],
        "case_kind": case["kind"],
        "evals_json_digest_sha256": case["evals_json_digest_sha256"],
        "git_sha": ledger["git_sha"],
        "harness": HARNESS,
        "model": worker["model"],
        "variant_id": worker["variant_id"],
    }
    if "fixture_digest_sha256" in case:
        pins["fixture_digest_sha256"] = case["fixture_digest_sha256"]
    return pins


def _validate_return(value: object, *, label: str) -> dict[str, Any]:
    payload = _object(value, location="worker return")
    _keys(payload, RETURN_KEYS, REQUIRED_RETURN_KEYS, location="worker return")
    returned = _label(payload["label"], location="worker return.label")
    if returned != label:
        raise EvidenceError(f"worker return label {returned!r} does not match file {label!r}")
    _text(payload["transcript_ref"], location="worker return.transcript_ref", max_len=400)
    _literal(payload["declaration"], DECLARATIONS, location="worker return.declaration")
    _sha256(payload["workspace_digest_sha256"], location="worker return.workspace_digest_sha256")
    if "changed_file_digests" in payload:
        changed = payload["changed_file_digests"]
        if not isinstance(changed, dict) or not all(
            isinstance(key, str) and SHA256_RE.fullmatch(str(digest) or "")
            for key, digest in changed.items()
        ):
            raise EvidenceError(
                "worker return.changed_file_digests must map paths to sha256 digests"
            )
    refuse_worker_facing(
        {
            "label": returned,
            "transcript_ref": payload["transcript_ref"],
        },
        f"{RETURNS_DIR}/{label}.json",
        payload["transcript_ref"],
    )
    return payload


def admit(run_dir: Path, label: str, workspace: Path) -> dict[str, Any]:
    ledger = load_ledger(run_dir)
    worker = _worker_for(ledger, label)
    source = run_dir / RETURNS_DIR / f"{label}.json"
    admitted_path = run_dir / ADMITTED_DIR / f"{label}.json"
    if admitted_path.exists():
        raise EvidenceError(f"worker {label!r} is already admitted")
    payload = _validate_return(_load_json(source, label="worker return"), label=label)
    transcript = _safe_under(workspace, payload["transcript_ref"], location="transcript_ref")
    if not transcript.is_file():
        raise EvidenceError(f"missing transcript: {transcript}")
    digest = file_digest(transcript)
    outputs: dict[str, Any] = {
        "transcript_ref": payload["transcript_ref"],
        "transcript_digest_sha256": digest,
        "declaration": payload["declaration"],
        "workspace_digest_sha256": payload["workspace_digest_sha256"],
    }
    if "changed_file_digests" in payload:
        outputs["changed_file_digests"] = payload["changed_file_digests"]
    admitted = {
        "schema_version": SCHEMA_VERSION,
        "admission": "admitted",
        "pins": _pins(ledger, worker),
        "outputs": outputs,
        "sanitized_label": label,
    }
    _write_json(admitted_path, admitted)
    return admitted


def load_admitted(run_dir: Path) -> list[dict[str, Any]]:
    directory = run_dir / ADMITTED_DIR
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = _object(_load_json(path, label="admitted run"), location=path.name)
        if payload.get("admission") != "admitted":
            raise EvidenceError(f"{path.name} is not an admitted run")
        label = _label(payload.get("sanitized_label"), location=f"{path.name}.sanitized_label")
        if path.stem != label:
            raise EvidenceError(f"{path.name} must be identity-named {label}.json")
        rows.append(payload)
    return rows


def _as_aggregation(value: str) -> Aggregation:
    if value == "rank-all":
        return "rank-all"
    if value == "first-pass":
        return "first-pass"
    if value == "best-of":
        return "best-of"
    raise EvidenceError(f"unknown aggregation: {value}")


def aggregation_limits(aggregation: Aggregation) -> tuple[str, ...]:
    if aggregation == "rank-all":
        return ()
    if aggregation == "first-pass":
        return (LIMIT_FIRST_PASS,)
    if aggregation == "best-of":
        return (LIMIT_BEST_OF,)
    _unhandled(aggregation)


def compute_limits(ledger: Mapping[str, Any], admitted: Sequence[Mapping[str, Any]]) -> list[str]:
    validate_spec(ledger)
    limits = list(ALWAYS_HELD)
    limits.extend(aggregation_limits(_as_aggregation(str(ledger["aggregation"]))))
    min_sample = (
        ledger["min_sample"] if isinstance(ledger.get("min_sample"), int) else DEFAULT_MIN_SAMPLE
    )
    if len(admitted) < min_sample:
        limits.append(LIMIT_SAMPLE_SIZE)
    if not ledger.get("judge_present", False):
        limits.append(LIMIT_MISSING_JUDGE)
    if ledger.get("platform_cap", False):
        limits.append(LIMIT_PLATFORM_CAP)
    return limits


def promote_refused(limits: list[str]) -> bool:
    return LIMIT_NO_AUTO_PROMOTE in limits or LIMIT_FIRST_PASS in limits or LIMIT_BEST_OF in limits


def summarize(
    ledger: Mapping[str, Any],
    admitted: Sequence[Mapping[str, Any]],
    *,
    author: str,
    notes: str,
    verdict: str,
) -> dict[str, Any]:
    limits = compute_limits(ledger, admitted)
    chosen = _literal(verdict, VERDICTS, location="verdict")
    if chosen == "promote" and promote_refused(limits):
        raise EvidenceError("chats alone cannot go green; promote is refused")
    _text(author, location="author", max_len=100)
    _text(notes, location="notes", max_len=8000)
    return {
        "schema_version": SCHEMA_VERSION,
        "skill_name": ledger["skill_name"],
        "mode": ledger["mode"],
        "aggregation": ledger["aggregation"],
        "verdict": chosen,
        "limits_held": limits,
        "run_labels": [row["sanitized_label"] for row in admitted],
        "author": author,
        "notes": notes,
    }


def check_summary(
    summary: object, ledger: Mapping[str, Any], admitted: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    payload = _object(summary, location="summary")
    allowed = frozenset(
        {
            "schema_version",
            "skill_name",
            "mode",
            "aggregation",
            "verdict",
            "limits_held",
            "run_labels",
            "author",
            "notes",
        }
    )
    required = frozenset(
        {
            "schema_version",
            "skill_name",
            "mode",
            "aggregation",
            "verdict",
            "limits_held",
            "author",
            "notes",
        }
    )
    _keys(payload, allowed, required, location="summary")
    expected = summarize(
        ledger,
        admitted,
        author=_text(payload["author"], location="summary.author", max_len=100),
        notes=_text(payload["notes"], location="summary.notes", max_len=8000),
        verdict=_literal(payload["verdict"], VERDICTS, location="summary.verdict"),
    )
    for key in ("schema_version", "skill_name", "mode", "aggregation", "verdict", "limits_held"):
        if payload[key] != expected[key]:
            raise EvidenceError(f"summary.{key} does not match computed evidence")
    if payload.get("run_labels", expected["run_labels"]) != expected["run_labels"]:
        raise EvidenceError("summary.run_labels do not match admitted labels")
    return expected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    emit_parser = sub.add_parser("emit", help="Write worker tasks and a sealed ledger")
    emit_parser.add_argument("--spec", type=Path, required=True)
    emit_parser.add_argument("--run-dir", type=Path, required=True)

    admit_parser = sub.add_parser("admit", help="Admit one identity-named worker return")
    admit_parser.add_argument("--run-dir", type=Path, required=True)
    admit_parser.add_argument("--label", required=True)
    admit_parser.add_argument("--workspace", type=Path, required=True)

    summarize_parser = sub.add_parser(
        "summarize", help="Fold admitted runs into an EvidenceSummary"
    )
    summarize_parser.add_argument("--run-dir", type=Path, required=True)
    summarize_parser.add_argument("--author", required=True)
    summarize_parser.add_argument("--notes", required=True)
    summarize_parser.add_argument("--verdict", choices=VERDICTS, required=True)
    summarize_parser.add_argument("--out", type=Path, required=True)

    check_parser = sub.add_parser(
        "check", help="Check a human EvidenceSummary against admitted runs"
    )
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--summary", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "emit":
            emit(_load_json(args.spec, label="spec"), args.run_dir)
            return 0
        if args.command == "admit":
            admit(args.run_dir, args.label, args.workspace)
            return 0
        if args.command == "summarize":
            ledger = load_ledger(args.run_dir)
            summary = summarize(
                ledger,
                load_admitted(args.run_dir),
                author=args.author,
                notes=args.notes,
                verdict=args.verdict,
            )
            _write_json(args.out, summary)
            return 0
        if args.command == "check":
            check_summary(
                _load_json(args.summary, label="summary"),
                load_ledger(args.run_dir),
                load_admitted(args.run_dir),
            )
            return 0
        raise EvidenceError(f"unknown command: {args.command}")
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
