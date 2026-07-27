"""Core models, fixture handling, metrics, and result aggregation."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard


class EvalError(RuntimeError):
    """Raised for a user-actionable evaluator configuration error."""


RUNTIME_EXCLUDED_NAMES = frozenset({"evals", "working", "__pycache__", ".git"})
BEHAVIOR_SUMMARY_RESERVED_KEYS = frozenset(
    {
        "absolute_lift",
        "lift_percentage_points",
        "paired_checks",
        "comparisons",
        "case_pass_rate",
        "behavior_activation_rate",
        "efficiency",
        "cases",
        "graded_cases",
    }
)
CHECK_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
CHECK_CLASSES = frozenset({"quality", "correctness", "safety", "local-contract"})
CHECK_GATES = frozenset({"normal", "hard"})
FIXTURE_FIDELITIES = frozenset(
    {"none", "files", "executable", "description-only", "degraded", "missing", "setup-failed"}
)
CONTEXT_REDUCTION_METRICS = frozenset(
    {
        "description_characters",
        "skill_md_body_characters",
        "runtime_package_bytes",
        "dynamic_input_tokens",
    }
)


def _runtime_package_files(path: Path, *, exclude: Iterable[str] = ()) -> tuple[Path, ...]:
    """Return the regular files included in a deterministic runtime package."""
    excluded = set(exclude)
    return tuple(
        item
        for item in sorted(path.rglob("*"), key=lambda entry: entry.as_posix())
        if item.is_file()
        and not item.is_symlink()
        and not any(part in excluded for part in item.relative_to(path).parts)
    )


@dataclass(frozen=True)
class TriggerCase:
    id: str
    query: str
    should_trigger: bool


@dataclass(frozen=True)
class BehaviorCheck:
    id: str
    text: str
    check_class: str = "quality"
    gate: str = "normal"
    structured: bool = True

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "text": self.text,
            "class": self.check_class,
            "gate": self.gate,
        }

    def report_value(self) -> str | dict[str, str]:
        return self.as_dict() if self.structured else self.text


@dataclass(frozen=True)
class ReviewPolicy:
    minimum_trigger_repeats: int = 2
    minimum_behavior_repeats: int = 2
    quality_non_inferiority_margin: float = 0.05
    minimum_lift_over_baseline: float = 0.05
    minimum_evidence_coverage: float = 1.0
    recall_non_inferiority_margin: float = 0.05
    specificity_non_inferiority_margin: float = 0.05
    minimum_context_reductions: tuple[tuple[str, int], ...] = (
        ("description_characters", 20),
        ("skill_md_body_characters", 100),
        ("runtime_package_bytes", 1024),
        ("dynamic_input_tokens", 100),
    )
    allowed_fixture_fidelity: tuple[str, ...] = (
        "none",
        "files",
        "executable",
        "description-only",
    )
    require_fixture_parity: bool = True
    require_blind_grading: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "minimum_repeats": {
                "trigger": self.minimum_trigger_repeats,
                "behavior": self.minimum_behavior_repeats,
            },
            "quality": {
                "non_inferiority_margin": self.quality_non_inferiority_margin,
                "minimum_lift_over_baseline": self.minimum_lift_over_baseline,
                "minimum_evidence_coverage": self.minimum_evidence_coverage,
            },
            "triggering": {
                "recall_non_inferiority_margin": self.recall_non_inferiority_margin,
                "specificity_non_inferiority_margin": self.specificity_non_inferiority_margin,
            },
            "context": {
                "minimum_reductions": dict(self.minimum_context_reductions),
            },
            "integrity": {
                "allowed_fixture_fidelity": list(self.allowed_fixture_fidelity),
                "require_fixture_parity": self.require_fixture_parity,
                "require_blind_grading": self.require_blind_grading,
            },
        }


@dataclass(frozen=True)
class BehaviorCase:
    id: str
    prompt: str
    expected_behavior: str
    fixtures: tuple[str, ...]
    checks: tuple[BehaviorCheck, ...]

    def __post_init__(self) -> None:
        normalized = tuple(
            check
            if isinstance(check, BehaviorCheck)
            else parse_behavior_check(
                check,
                case_id=self.id,
                index=index,
                location=f"behavior case {self.id} check {index + 1}",
            )
            for index, check in enumerate(self.checks)
        )
        object.__setattr__(self, "checks", normalized)


@dataclass(frozen=True)
class EvalSpec:
    skill_name: str
    trigger_cases: tuple[TriggerCase, ...]
    behavior_cases: tuple[BehaviorCase, ...]
    review_policy: ReviewPolicy | None
    path: Path


@dataclass(frozen=True)
class EvaluationCondition:
    """One immutable runtime package selection in an evaluation."""

    id: str
    runtime_skill_dir: Path | None
    runtime_digest_sha256: str | None
    installation_name: str
    display_label: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.id, "condition id"),
            (self.installation_name, "condition installation name"),
            (self.display_label, "condition display label"),
        ):
            if not value.strip():
                raise EvalError(f"{field_name} must not be empty")
        if self.id in {".", ".."} or "/" in self.id or "\\" in self.id or "\0" in self.id:
            raise EvalError("condition id must be a safe path segment")
        if (
            self.installation_name in {".", ".."}
            or "/" in self.installation_name
            or "\\" in self.installation_name
            or "\0" in self.installation_name
        ):
            raise EvalError("condition installation name must be a safe path segment")
        if self.runtime_skill_dir is None and self.runtime_digest_sha256 is not None:
            raise EvalError("condition runtime digest requires a runtime skill directory")
        if self.runtime_skill_dir is not None and not self.runtime_digest_sha256:
            raise EvalError("condition runtime skill directory requires a runtime digest")


def _case_id(value: object, *, location: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise EvalError(f"{location} id must be a string or integer")
    result = str(value).strip()
    if not result:
        raise EvalError(f"{location} id must not be empty")
    if result in {".", ".."} or "/" in result or "\\" in result or "\0" in result:
        raise EvalError(f"{location} id must be a safe path segment")
    return result


def parse_behavior_check(
    value: object,
    *,
    case_id: str,
    index: int,
    location: str,
) -> BehaviorCheck:
    """Parse a legacy string or metadata-bearing behavior check."""
    if isinstance(value, str):
        if not value.strip():
            raise EvalError(f"{location} must be a non-empty string or check object")
        return BehaviorCheck(
            id=f"{case_id}-check-{index + 1}",
            text=value,
            structured=False,
        )
    if not isinstance(value, dict):
        raise EvalError(f"{location} must be a non-empty string or check object")
    required = {"id", "text", "class", "gate"}
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        raise EvalError(f"{location} must contain id, text, class, and gate ({'; '.join(detail)})")
    check_id = value["id"]
    text = value["text"]
    check_class = value["class"]
    gate = value["gate"]
    if not isinstance(check_id, str) or not CHECK_ID_RE.fullmatch(check_id):
        raise EvalError(
            f"{location}.id must be a stable lowercase kebab-case identifier "
            "between 1 and 64 characters"
        )
    if not isinstance(text, str) or not text.strip():
        raise EvalError(f"{location}.text must be a non-empty string")
    if check_class not in CHECK_CLASSES:
        raise EvalError(f"{location}.class must be one of: {', '.join(sorted(CHECK_CLASSES))}")
    if gate not in CHECK_GATES:
        raise EvalError(f"{location}.gate must be one of: {', '.join(sorted(CHECK_GATES))}")
    return BehaviorCheck(
        id=check_id,
        text=text,
        check_class=check_class,
        gate=gate,
    )


def _policy_object(value: object, *, location: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise EvalError(f"{location} must be an object")
    return value


def _policy_number(
    value: object,
    default: float,
    *,
    location: str,
    maximum: float = 1.0,
) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvalError(f"{location} must be a number between 0 and {maximum:g}")
    result = float(value)
    if not 0 <= result <= maximum:
        raise EvalError(f"{location} must be between 0 and {maximum:g}")
    return result


def _policy_positive_int(value: object, default: int, *, location: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvalError(f"{location} must be a positive integer")
    return value


def _reject_policy_keys(value: dict[str, Any], allowed: set[str], *, location: str) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        raise EvalError(f"{location} contains unexpected keys: {', '.join(extra)}")


def parse_review_policy(value: object) -> ReviewPolicy:
    """Validate and default a repository-owned optimisation review policy."""
    root = _policy_object(value, location="review_policy")
    _reject_policy_keys(
        root,
        {"minimum_repeats", "quality", "triggering", "context", "integrity"},
        location="review_policy",
    )
    defaults = ReviewPolicy()
    repeats = _policy_object(root.get("minimum_repeats"), location="review_policy.minimum_repeats")
    quality = _policy_object(root.get("quality"), location="review_policy.quality")
    triggering = _policy_object(root.get("triggering"), location="review_policy.triggering")
    context = _policy_object(root.get("context"), location="review_policy.context")
    integrity = _policy_object(root.get("integrity"), location="review_policy.integrity")
    _reject_policy_keys(
        repeats,
        {"trigger", "behavior"},
        location="review_policy.minimum_repeats",
    )
    _reject_policy_keys(
        quality,
        {
            "non_inferiority_margin",
            "minimum_lift_over_baseline",
            "minimum_evidence_coverage",
        },
        location="review_policy.quality",
    )
    _reject_policy_keys(
        triggering,
        {
            "recall_non_inferiority_margin",
            "specificity_non_inferiority_margin",
        },
        location="review_policy.triggering",
    )
    _reject_policy_keys(
        context,
        {"minimum_reductions"},
        location="review_policy.context",
    )
    _reject_policy_keys(
        integrity,
        {
            "allowed_fixture_fidelity",
            "require_fixture_parity",
            "require_blind_grading",
        },
        location="review_policy.integrity",
    )

    reductions_value = context.get("minimum_reductions")
    if reductions_value is None:
        reductions = defaults.minimum_context_reductions
    else:
        reductions_object = _policy_object(
            reductions_value,
            location="review_policy.context.minimum_reductions",
        )
        unknown_metrics = sorted(set(reductions_object) - CONTEXT_REDUCTION_METRICS)
        if unknown_metrics:
            raise EvalError(
                "review_policy.context.minimum_reductions contains unknown metrics: "
                + ", ".join(unknown_metrics)
            )
        if not reductions_object:
            raise EvalError("review_policy.context.minimum_reductions must not be empty")
        parsed_reductions: list[tuple[str, int]] = []
        for metric, threshold in reductions_object.items():
            if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold <= 0:
                raise EvalError(
                    "review_policy.context.minimum_reductions values must be positive integers"
                )
            parsed_reductions.append((metric, threshold))
        reductions = tuple(sorted(parsed_reductions))

    fidelity_value = integrity.get("allowed_fixture_fidelity")
    if fidelity_value is None:
        allowed_fidelity = defaults.allowed_fixture_fidelity
    else:
        if (
            not isinstance(fidelity_value, list)
            or not fidelity_value
            or not all(isinstance(item, str) for item in fidelity_value)
        ):
            raise EvalError(
                "review_policy.integrity.allowed_fixture_fidelity must be a "
                "non-empty list of fidelity names"
            )
        invalid_fidelity = sorted(set(fidelity_value) - FIXTURE_FIDELITIES)
        if invalid_fidelity:
            raise EvalError(
                "review_policy.integrity.allowed_fixture_fidelity contains unknown values: "
                + ", ".join(invalid_fidelity)
            )
        if len(set(fidelity_value)) != len(fidelity_value):
            raise EvalError(
                "review_policy.integrity.allowed_fixture_fidelity must not contain duplicates"
            )
        allowed_fidelity = tuple(fidelity_value)

    def policy_bool(key: str, default: bool) -> bool:
        supplied = integrity.get(key)
        if supplied is None:
            return default
        if not isinstance(supplied, bool):
            raise EvalError(f"review_policy.integrity.{key} must be boolean")
        return supplied

    return ReviewPolicy(
        minimum_trigger_repeats=_policy_positive_int(
            repeats.get("trigger"),
            defaults.minimum_trigger_repeats,
            location="review_policy.minimum_repeats.trigger",
        ),
        minimum_behavior_repeats=_policy_positive_int(
            repeats.get("behavior"),
            defaults.minimum_behavior_repeats,
            location="review_policy.minimum_repeats.behavior",
        ),
        quality_non_inferiority_margin=_policy_number(
            quality.get("non_inferiority_margin"),
            defaults.quality_non_inferiority_margin,
            location="review_policy.quality.non_inferiority_margin",
        ),
        minimum_lift_over_baseline=_policy_number(
            quality.get("minimum_lift_over_baseline"),
            defaults.minimum_lift_over_baseline,
            location="review_policy.quality.minimum_lift_over_baseline",
        ),
        minimum_evidence_coverage=_policy_number(
            quality.get("minimum_evidence_coverage"),
            defaults.minimum_evidence_coverage,
            location="review_policy.quality.minimum_evidence_coverage",
        ),
        recall_non_inferiority_margin=_policy_number(
            triggering.get("recall_non_inferiority_margin"),
            defaults.recall_non_inferiority_margin,
            location="review_policy.triggering.recall_non_inferiority_margin",
        ),
        specificity_non_inferiority_margin=_policy_number(
            triggering.get("specificity_non_inferiority_margin"),
            defaults.specificity_non_inferiority_margin,
            location="review_policy.triggering.specificity_non_inferiority_margin",
        ),
        minimum_context_reductions=reductions,
        allowed_fixture_fidelity=allowed_fidelity,
        require_fixture_parity=policy_bool(
            "require_fixture_parity",
            defaults.require_fixture_parity,
        ),
        require_blind_grading=policy_bool(
            "require_blind_grading",
            defaults.require_blind_grading,
        ),
    )


def discover_repository_skills(repo_root: Path) -> tuple[Path, ...]:
    """Return publishable skill packages from the repository skill root."""
    skills_root = repo_root.resolve() / "skills"
    if not skills_root.is_dir():
        return ()
    return tuple(
        sorted(
            (path.parent.resolve() for path in skills_root.glob("*/SKILL.md")),
            key=lambda path: str(path),
        )
    )


def resolve_skill(repo_root: Path, selector: str) -> Path:
    """Resolve a full id, short name, or skill directory path."""
    repo_root = repo_root.resolve()
    supplied = Path(selector).expanduser()
    direct_candidates = [supplied]
    if not supplied.is_absolute():
        direct_candidates.insert(0, repo_root / supplied)

    for candidate in direct_candidates:
        candidate = candidate.resolve()
        if (candidate / "SKILL.md").is_file():
            return candidate

    skills_root = repo_root / "skills"
    exact = (skills_root / selector).resolve()
    if (exact / "SKILL.md").is_file():
        return exact

    matches = [path for path in discover_repository_skills(repo_root) if path.name == selector]
    if not matches:
        raise EvalError(
            f"No skill matches {selector!r}. Use a short name such as 'commit', "
            "a repository path such as 'skills/commit', or a skill directory path."
        )
    if len(matches) > 1:
        display = ", ".join(str(path.relative_to(repo_root)) for path in matches)
        raise EvalError(f"Skill name {selector!r} is ambiguous: {display}")
    return matches[0]


def load_eval_spec(skill_dir: Path, evals_root: Path) -> EvalSpec:
    eval_path = evals_root.resolve() / skill_dir.name / "evals.json"
    try:
        payload = json.loads(eval_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvalError(f"Missing eval definition: {eval_path}") from exc
    except json.JSONDecodeError as exc:
        raise EvalError(f"Invalid JSON in {eval_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise EvalError(f"Eval definition must be a JSON object: {eval_path}")
    allowed_keys = {"skill_name", "trigger_evals", "behavior_evals", "review_policy"}
    unexpected = sorted(set(payload) - allowed_keys)
    if unexpected:
        raise EvalError(f"Unexpected eval definition keys in {eval_path}: {', '.join(unexpected)}")
    name = payload.get("skill_name")
    if name != skill_dir.name:
        raise EvalError(
            f"skill_name mismatch in {eval_path}: expected {skill_dir.name!r}, found {name!r}"
        )

    trigger_cases: list[TriggerCase] = []
    seen_trigger_ids: set[str] = set()
    for index, item in enumerate(payload.get("trigger_evals", []), start=1):
        if not isinstance(item, dict):
            raise EvalError(f"trigger_evals[{index}] must be an object")
        case_id = _case_id(item.get("id"), location=f"trigger_evals[{index}]")
        if case_id in seen_trigger_ids:
            raise EvalError(f"Duplicate trigger eval id: {case_id}")
        seen_trigger_ids.add(case_id)
        query = item.get("query")
        expected = item.get("should_trigger")
        if not isinstance(query, str) or not query.strip():
            raise EvalError(f"trigger_evals[{index}].query must be a non-empty string")
        if not isinstance(expected, bool):
            raise EvalError(f"trigger_evals[{index}].should_trigger must be boolean")
        trigger_cases.append(TriggerCase(case_id, query, expected))

    behavior_cases: list[BehaviorCase] = []
    seen_behavior_ids: set[str] = set()
    seen_structured_check_ids: set[str] = set()
    for index, item in enumerate(payload.get("behavior_evals", []), start=1):
        if not isinstance(item, dict):
            raise EvalError(f"behavior_evals[{index}] must be an object")
        case_id = _case_id(item.get("id"), location=f"behavior_evals[{index}]")
        if case_id in seen_behavior_ids:
            raise EvalError(f"Duplicate behavior eval id: {case_id}")
        seen_behavior_ids.add(case_id)
        prompt = item.get("prompt")
        expected_behavior = item.get("expected_behavior")
        fixtures = item.get("fixtures")
        checks = item.get("checks")
        if not isinstance(prompt, str) or not prompt.strip():
            raise EvalError(f"behavior_evals[{index}].prompt must be a non-empty string")
        if not isinstance(expected_behavior, str) or not expected_behavior.strip():
            raise EvalError(f"behavior_evals[{index}].expected_behavior must be a non-empty string")
        if not isinstance(fixtures, list) or not all(
            isinstance(x, str) and x.strip() for x in fixtures
        ):
            raise EvalError(f"behavior_evals[{index}].fixtures must be a list of non-empty strings")
        if not isinstance(checks, list) or not checks:
            raise EvalError(
                f"behavior_evals[{index}].checks must be a non-empty list of strings "
                "or check objects"
            )
        parsed_checks = tuple(
            parse_behavior_check(
                check,
                case_id=case_id,
                index=check_index,
                location=f"behavior_evals[{index}].checks[{check_index + 1}]",
            )
            for check_index, check in enumerate(checks)
        )
        for check in parsed_checks:
            if not check.structured:
                continue
            if check.id in seen_structured_check_ids:
                raise EvalError(f"Duplicate structured behavior check id: {check.id}")
            seen_structured_check_ids.add(check.id)
        behavior_cases.append(
            BehaviorCase(
                case_id,
                prompt,
                expected_behavior,
                tuple(fixtures),
                parsed_checks,
            )
        )

    if not trigger_cases and not behavior_cases:
        raise EvalError(f"No eval cases found in {eval_path}")
    review_policy = (
        parse_review_policy(payload["review_policy"]) if "review_policy" in payload else None
    )
    return EvalSpec(
        name,
        tuple(trigger_cases),
        tuple(behavior_cases),
        review_policy,
        eval_path,
    )


def stable_digest(path: Path, *, exclude: Iterable[str] = ()) -> str:
    """Hash a file tree deterministically without following symlinks."""
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for item in _runtime_package_files(path, exclude=exclude):
        relative = item.relative_to(path)
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _parse_skill_document(
    text: str,
    skill_md: Path,
    *,
    source: str,
) -> tuple[dict[str, Any], str]:
    """Parse canonical skill frontmatter and return its exact instruction body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n").strip() != "---":
        raise EvalError(f"{source} SKILL.md must start with YAML frontmatter: {skill_md}")
    closing = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.rstrip("\r\n").strip() == "---"
            and not line.rstrip("\r\n").startswith((" ", "\t"))
        ),
        None,
    )
    if closing is None:
        raise EvalError(f"{source} SKILL.md frontmatter is missing a closing delimiter: {skill_md}")

    import validate_repo

    previous_error_count = len(validate_repo.ERRORS)
    payload = validate_repo.parse_yaml_string_map(
        "".join(lines[1:closing]).rstrip("\r\n"),
        str(skill_md),
    )
    parse_errors = validate_repo.ERRORS[previous_error_count:]
    del validate_repo.ERRORS[previous_error_count:]
    if payload is None or parse_errors:
        detail = "; ".join(parse_errors) or "invalid YAML frontmatter"
        raise EvalError(f"{source} SKILL.md is malformed: {detail}")
    return payload, "".join(lines[closing + 1 :])


def measure_static_footprint(
    runtime_skill_dir: Path | None,
    runtime_digest_sha256: str | None,
) -> dict[str, Any]:
    """Measure portable static context without using a provider tokenizer."""
    if runtime_skill_dir is None:
        return {
            "description": {"characters": 0, "utf8_bytes": 0},
            "skill_md_body": {"characters": 0, "utf8_bytes": 0},
            "runtime_package": {
                "file_count": 0,
                "bytes": 0,
                "digest_sha256": None,
            },
        }

    skill_md = runtime_skill_dir / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EvalError(f"Missing runtime SKILL.md: {skill_md}") from exc
    except UnicodeDecodeError as exc:
        raise EvalError(f"Runtime SKILL.md must be UTF-8: {skill_md}") from exc

    payload, body = _parse_skill_document(text, skill_md, source="Runtime")
    description_value = payload.get("description", "")
    description = description_value.strip() if isinstance(description_value, str) else ""
    if not description:
        raise EvalError(f"Runtime SKILL.md is missing a non-empty description: {skill_md}")

    files = _runtime_package_files(runtime_skill_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    return {
        "description": {
            "characters": len(description),
            "utf8_bytes": len(description.encode("utf-8")),
        },
        "skill_md_body": {
            "characters": len(body),
            "utf8_bytes": len(body.encode("utf-8")),
        },
        "runtime_package": {
            "file_count": len(files),
            "bytes": sum(item.stat().st_size for item in files),
            "digest_sha256": runtime_digest_sha256,
        },
    }


def condition_static_footprints(
    conditions: tuple[EvaluationCondition, ...],
) -> dict[str, dict[str, Any]]:
    """Return static footprint evidence keyed by evaluation condition id."""
    return {
        condition.id: {
            "label": condition.display_label,
            "runtime_package_present": condition.runtime_skill_dir is not None,
            **measure_static_footprint(
                condition.runtime_skill_dir,
                condition.runtime_digest_sha256,
            ),
        }
        for condition in conditions
    }


def canonical_discovery_inputs(runtime_skill_dir: Path) -> dict[str, str]:
    """Return the canonical metadata inputs used for skill discovery."""
    skill_md = runtime_skill_dir / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EvalError(f"Missing runtime SKILL.md: {skill_md}") from exc
    except UnicodeDecodeError as exc:
        raise EvalError(f"Runtime SKILL.md must be UTF-8: {skill_md}") from exc

    payload, _body = _parse_skill_document(text, skill_md, source="Runtime")
    inputs: dict[str, str] = {}
    for field in ("name", "description"):
        value = payload.get(field)
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized:
            raise EvalError(
                f"Runtime SKILL.md is missing a non-empty canonical {field}: {skill_md}"
            )
        inputs[field] = normalized
    return inputs


def compare_candidate_discovery_inputs(
    conditions: tuple[EvaluationCondition, ...],
) -> dict[str, Any]:
    """Compare Current and Candidate inputs that can affect discovery."""
    by_id = {condition.id: condition for condition in conditions}
    try:
        current_dir = by_id["skill"].runtime_skill_dir
        candidate_dir = by_id["candidate"].runtime_skill_dir
    except KeyError as exc:
        raise EvalError(
            "candidate discovery comparison requires skill and candidate conditions"
        ) from exc
    if current_dir is None or candidate_dir is None:
        raise EvalError("candidate discovery comparison requires two runtime skill packages")

    current = canonical_discovery_inputs(current_dir)
    candidate = canonical_discovery_inputs(candidate_dir)
    changed_fields = [
        field for field in ("name", "description") if current[field] != candidate[field]
    ]
    return {
        "canonical_fields": ["name", "description"],
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "trigger_gate_mode": "blocking" if changed_fields else "observational",
    }


def summarize_candidate_comparison(
    behavior_summary: dict[str, Any] | None,
    static_footprints: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Combine candidate quality and positive-means-reduction context deltas."""
    current_static = static_footprints["skill"]
    candidate_static = static_footprints["candidate"]

    def reduction(section: str, field: str) -> int:
        return int(current_static[section][field]) - int(candidate_static[section][field])

    candidate_vs_current = None
    candidate_vs_baseline = None
    current_efficiency = None
    candidate_efficiency = None
    if behavior_summary is not None:
        comparisons = behavior_summary.get("comparisons", {})
        candidate_vs_current = comparisons.get("candidate_vs_current")
        candidate_vs_baseline = comparisons.get("candidate_vs_baseline")
        efficiency = behavior_summary.get("efficiency", {})
        current_efficiency = efficiency.get("skill")
        candidate_efficiency = efficiency.get("candidate")

    input_token_reduction = None
    if current_efficiency is not None and candidate_efficiency is not None:
        current_input = current_efficiency.get("input_tokens")
        candidate_input = candidate_efficiency.get("input_tokens")
        current_completed = current_efficiency.get("completed_runs")
        candidate_completed = candidate_efficiency.get("completed_runs")
        fully_paired = (
            isinstance(current_completed, int)
            and current_completed == candidate_completed
            and current_efficiency.get("failed_runs") == 0
            and candidate_efficiency.get("failed_runs") == 0
        )
        if fully_paired and isinstance(current_input, int) and isinstance(candidate_input, int):
            input_token_reduction = current_input - candidate_input

    paired = candidate_vs_current.get("paired_checks") if candidate_vs_current else None
    return {
        "sign_convention": {
            "quality": "candidate minus comparison; positive means candidate quality is higher",
            "reduction": "current minus candidate; positive means candidate context is smaller",
        },
        "candidate_minus_current_quality": (
            candidate_vs_current.get("absolute_lift") if candidate_vs_current else None
        ),
        "candidate_minus_current_quality_percentage_points": (
            candidate_vs_current.get("lift_percentage_points") if candidate_vs_current else None
        ),
        "candidate_lift_over_baseline": (
            candidate_vs_baseline.get("absolute_lift") if candidate_vs_baseline else None
        ),
        "candidate_lift_over_baseline_percentage_points": (
            candidate_vs_baseline.get("lift_percentage_points") if candidate_vs_baseline else None
        ),
        "static_reductions": {
            "description_characters": reduction("description", "characters"),
            "description_utf8_bytes": reduction("description", "utf8_bytes"),
            "skill_md_body_characters": reduction("skill_md_body", "characters"),
            "skill_md_body_utf8_bytes": reduction("skill_md_body", "utf8_bytes"),
            "runtime_package_files": reduction("runtime_package", "file_count"),
            "runtime_package_bytes": reduction("runtime_package", "bytes"),
        },
        "dynamic_input_token_reduction": input_token_reduction,
        "paired_checks": {
            "wins": paired["left_wins"] if paired else 0,
            "regressions": paired["right_wins"] if paired else 0,
            "ties": paired["ties"] if paired else 0,
            "unknown": paired["unknown"] if paired else 0,
        },
    }


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def summarize_optimisation_review(
    *,
    policy: ReviewPolicy | None,
    behavior_cases: tuple[BehaviorCase, ...],
    behavior_results: list[dict[str, Any]],
    behavior_summary: dict[str, Any] | None,
    current_trigger_summary: dict[str, Any] | None,
    candidate_trigger_summary: dict[str, Any] | None,
    candidate_comparison: dict[str, Any],
    configured_trigger_case_ids: tuple[str, ...],
    selected_trigger_case_ids: tuple[str, ...],
    configured_behavior_case_ids: tuple[str, ...],
    selected_behavior_case_ids: tuple[str, ...],
    trigger_repeats: int,
    behavior_repeats: int,
    fixture_parity: bool | None,
    blind_grading: bool,
    discovery_input_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate independent hard gates for a candidate optimisation review."""
    effective_policy = policy or ReviewPolicy()
    dimensions: dict[str, dict[str, Any]] = {
        name: {"status": "not-applicable", "gates": []}
        for name in ("correctness", "safety", "triggering", "context", "integrity")
    }

    def add_gate(
        dimension: str,
        gate_id: str,
        status: str,
        *,
        observed: object,
        required: object,
        detail: str,
        hard: bool = True,
    ) -> None:
        dimensions[dimension]["gates"].append(
            {
                "id": gate_id,
                "status": status,
                "hard": hard,
                "observed": observed,
                "required": required,
                "detail": detail,
            }
        )

    comparisons = behavior_summary.get("comparisons", {}) if behavior_summary else {}
    candidate_vs_current = comparisons.get("candidate_vs_current")
    quality_delta = candidate_vs_current.get("absolute_lift") if candidate_vs_current else None
    quality_required = -effective_policy.quality_non_inferiority_margin
    quality_status = (
        "pass"
        if _is_number(quality_delta) and quality_delta >= quality_required
        else "fail"
        if _is_number(quality_delta)
        else "insufficient-evidence"
    )
    add_gate(
        "correctness",
        "candidate-non-inferiority",
        quality_status,
        observed=quality_delta,
        required={"minimum_candidate_minus_current": quality_required},
        detail="Candidate quality must remain within the configured margin of Current.",
    )

    candidate_vs_baseline = comparisons.get("candidate_vs_baseline")
    baseline_lift = candidate_vs_baseline.get("absolute_lift") if candidate_vs_baseline else None
    baseline_status = (
        "pass"
        if _is_number(baseline_lift)
        and baseline_lift >= effective_policy.minimum_lift_over_baseline
        else "fail"
        if _is_number(baseline_lift)
        else "insufficient-evidence"
    )
    add_gate(
        "correctness",
        "retained-skill-baseline-value",
        baseline_status,
        observed=baseline_lift,
        required={
            "minimum_candidate_lift_over_baseline": (effective_policy.minimum_lift_over_baseline)
        },
        detail="A retained candidate must show the configured value over Baseline.",
    )

    def check_value(
        items: list[dict[str, Any]],
        check_id: str,
        fallback_index: int,
    ) -> bool | None:
        identified = next(
            (item for item in items if item.get("check_id") == check_id),
            None,
        )
        if identified is not None:
            return identified.get("passed")
        if any("check_id" in item for item in items):
            return None
        return items[fallback_index].get("passed") if fallback_index < len(items) else None

    for case in behavior_cases:
        matching_results = [
            result for result in behavior_results if result.get("case_id") == case.id
        ]
        for index, check in enumerate(case.checks):
            if check.gate != "hard":
                continue
            current_values: list[bool | None] = []
            candidate_values: list[bool | None] = []
            for result in matching_results:
                grades = result.get("grades", {})
                current_items = grades.get("skill", [])
                candidate_items = grades.get("candidate", [])
                current_values.append(check_value(current_items, check.id, index))
                candidate_values.append(check_value(candidate_items, check.id, index))
            candidate_failures = sum(value is False for value in candidate_values)
            regressions = sum(
                current is True and candidate is False
                for current, candidate in zip(
                    current_values,
                    candidate_values,
                    strict=False,
                )
            )
            unknown = sum(
                current is None or candidate is None
                for current, candidate in zip(
                    current_values,
                    candidate_values,
                    strict=False,
                )
            )
            protected_status = (
                "fail"
                if candidate_failures
                else "insufficient-evidence"
                if not matching_results or unknown
                else "pass"
            )
            protected_dimension = "safety" if check.check_class == "safety" else "correctness"
            add_gate(
                protected_dimension,
                f"protected-check:{check.id}",
                protected_status,
                observed={
                    "candidate_failures": candidate_failures,
                    "regressions": regressions,
                    "unknown_pairs": unknown,
                    "evaluated_pairs": len(matching_results),
                },
                required={
                    "candidate_failures": 0,
                    "regressions": 0,
                    "unknown_pairs": 0,
                },
                detail=(
                    f"Protected {check.check_class} check: {check.text} "
                    "Unknown evidence never counts as a pass."
                ),
            )

    def trigger_gate(metric: str, margin: float) -> None:
        current_value = current_trigger_summary.get(metric) if current_trigger_summary else None
        candidate_value = (
            candidate_trigger_summary.get(metric) if candidate_trigger_summary else None
        )
        delta = (
            candidate_value - current_value
            if _is_number(current_value) and _is_number(candidate_value)
            else None
        )
        status = (
            "pass"
            if _is_number(delta) and delta >= -margin
            else "fail"
            if _is_number(delta)
            else "insufficient-evidence"
        )
        discovery_inputs_changed = (
            discovery_input_comparison.get("changed")
            if isinstance(discovery_input_comparison, dict)
            else True
        )
        blocking = discovery_inputs_changed is not False
        add_gate(
            "triggering",
            f"{metric}-non-inferiority",
            status,
            observed={
                "current": current_value,
                "candidate": candidate_value,
                "candidate_minus_current": delta,
            },
            required={"minimum_candidate_minus_current": -margin},
            detail=(
                f"Candidate trigger {metric} must stay within the configured margin "
                "because canonical discovery inputs changed."
                if blocking
                else f"Candidate trigger {metric} variance is observational because "
                "canonical discovery inputs are unchanged."
            ),
            hard=blocking,
        )

    trigger_gate("recall", effective_policy.recall_non_inferiority_margin)
    trigger_gate("specificity", effective_policy.specificity_non_inferiority_margin)

    reductions = {
        **candidate_comparison.get("static_reductions", {}),
        "dynamic_input_tokens": candidate_comparison.get("dynamic_input_token_reduction"),
    }
    thresholds = dict(effective_policy.minimum_context_reductions)
    satisfied = [
        metric
        for metric, threshold in thresholds.items()
        if _is_number(reductions.get(metric)) and reductions[metric] >= threshold
    ]
    known_reductions = [metric for metric in thresholds if _is_number(reductions.get(metric))]
    context_status = (
        "pass" if satisfied else "fail" if known_reductions else "insufficient-evidence"
    )
    add_gate(
        "context",
        "meaningful-context-reduction",
        context_status,
        observed={"reductions": reductions, "thresholds_met": satisfied},
        required={"at_least_one_minimum_reduction": thresholds},
        detail="At least one configured context reduction must be met.",
    )

    add_gate(
        "integrity",
        "repository-review-policy",
        "pass" if policy is not None else "insufficient-evidence",
        observed="configured" if policy is not None else "missing",
        required="configured",
        detail=(
            "Missing policy uses conservative values for reporting only and can "
            "never approve an optimisation."
        ),
    )
    complete_trigger_suite = (
        bool(configured_trigger_case_ids)
        and len(selected_trigger_case_ids) == len(configured_trigger_case_ids)
        and set(selected_trigger_case_ids) == set(configured_trigger_case_ids)
    )
    complete_behavior_suite = (
        bool(configured_behavior_case_ids)
        and len(selected_behavior_case_ids) == len(configured_behavior_case_ids)
        and set(selected_behavior_case_ids) == set(configured_behavior_case_ids)
    )
    add_gate(
        "integrity",
        "complete-suite-coverage",
        "pass"
        if current_trigger_summary is not None
        and candidate_trigger_summary is not None
        and behavior_summary is not None
        and complete_trigger_suite
        and complete_behavior_suite
        else "insufficient-evidence",
        observed={
            "trigger": {
                "configured_case_ids": list(configured_trigger_case_ids),
                "selected_case_ids": list(selected_trigger_case_ids),
                "complete": complete_trigger_suite,
                "current_summary": current_trigger_summary is not None,
                "candidate_summary": candidate_trigger_summary is not None,
            },
            "behavior": {
                "configured_case_ids": list(configured_behavior_case_ids),
                "selected_case_ids": list(selected_behavior_case_ids),
                "complete": complete_behavior_suite,
                "summary": behavior_summary is not None,
            },
        },
        required={
            "all_configured_trigger_cases": True,
            "all_configured_behavior_cases": True,
            "current_trigger_summary": True,
            "candidate_trigger_summary": True,
            "behavior_summary": True,
        },
        detail=(
            "Optimisation approval requires every configured trigger and behavior "
            "case; filtered or capped suites remain report-only."
        ),
    )
    add_gate(
        "integrity",
        "minimum-trigger-repeats",
        "pass"
        if current_trigger_summary is not None
        and candidate_trigger_summary is not None
        and trigger_repeats >= effective_policy.minimum_trigger_repeats
        else "insufficient-evidence",
        observed=trigger_repeats if current_trigger_summary is not None else None,
        required=effective_policy.minimum_trigger_repeats,
        detail="Trigger evidence must meet the policy's minimum repeat count.",
    )
    add_gate(
        "integrity",
        "minimum-behavior-repeats",
        "pass"
        if behavior_summary is not None
        and behavior_repeats >= effective_policy.minimum_behavior_repeats
        else "insufficient-evidence",
        observed=behavior_repeats if behavior_summary is not None else None,
        required=effective_policy.minimum_behavior_repeats,
        detail="Behavior evidence must meet the policy's minimum repeat count.",
    )

    evidence_coverage = {
        condition: (
            behavior_summary.get(condition, {}).get("evidence_coverage")
            if behavior_summary is not None
            else None
        )
        for condition in ("skill", "baseline", "candidate")
    }
    coverage_values = list(evidence_coverage.values())
    coverage_status = (
        "pass"
        if all(
            _is_number(value) and value >= effective_policy.minimum_evidence_coverage
            for value in coverage_values
        )
        else "insufficient-evidence"
    )
    add_gate(
        "integrity",
        "behavior-evidence-coverage",
        coverage_status,
        observed=evidence_coverage,
        required={"minimum_each": effective_policy.minimum_evidence_coverage},
        detail=(
            "Current, Baseline, and Candidate need the configured evidence coverage independently."
        ),
    )

    current_trigger_errors = (
        current_trigger_summary.get("run_errors") if current_trigger_summary is not None else None
    )
    candidate_trigger_errors = (
        candidate_trigger_summary.get("run_errors")
        if candidate_trigger_summary is not None
        else None
    )
    behavior_errors = (
        {
            condition: behavior_summary.get("efficiency", {}).get(condition, {}).get("failed_runs")
            for condition in ("skill", "baseline", "candidate")
        }
        if behavior_summary is not None
        else {}
    )
    execution_error_values = [
        current_trigger_errors,
        candidate_trigger_errors,
        *behavior_errors.values(),
    ]
    execution_status = (
        "pass"
        if all(value == 0 for value in execution_error_values)
        else "fail"
        if all(isinstance(value, int) for value in execution_error_values)
        else "insufficient-evidence"
    )
    add_gate(
        "integrity",
        "execution-completeness",
        execution_status,
        observed={
            "current_trigger_errors": current_trigger_errors,
            "candidate_trigger_errors": candidate_trigger_errors,
            "behavior_failed_runs": behavior_errors,
        },
        required="zero run errors for every condition",
        detail="Incomplete task runs cannot establish an optimisation result.",
    )

    judge_statuses = [result.get("judge", {}).get("status") for result in behavior_results]
    add_gate(
        "integrity",
        "judgment-completeness",
        "pass"
        if judge_statuses and all(status == "completed" for status in judge_statuses)
        else "fail"
        if judge_statuses
        else "insufficient-evidence",
        observed=judge_statuses,
        required="completed judgment for every behavior repeat",
        detail="Every behavior repeat needs a valid condition-blind judgment.",
    )

    fixture_fidelity = sorted(
        {
            str(result.get("fixture_fidelity"))
            for result in behavior_results
            if result.get("fixture_fidelity") is not None
        }
    )
    fidelity_status = (
        "pass"
        if fixture_fidelity
        and set(fixture_fidelity).issubset(effective_policy.allowed_fixture_fidelity)
        else "fail"
        if fixture_fidelity
        else "insufficient-evidence"
    )
    add_gate(
        "integrity",
        "fixture-fidelity",
        fidelity_status,
        observed=fixture_fidelity,
        required={"allowed": list(effective_policy.allowed_fixture_fidelity)},
        detail="Every behavior repeat must use a policy-allowed fixture fidelity.",
    )
    add_gate(
        "integrity",
        "fixture-parity",
        "pass"
        if not effective_policy.require_fixture_parity or fixture_parity is True
        else "fail"
        if fixture_parity is False
        else "insufficient-evidence",
        observed=fixture_parity,
        required=effective_policy.require_fixture_parity,
        detail="All conditions must receive equivalent fixture state when required.",
    )
    add_gate(
        "integrity",
        "condition-blind-grading",
        "pass" if not effective_policy.require_blind_grading or blind_grading else "fail",
        observed=blind_grading,
        required=effective_policy.require_blind_grading,
        detail="Condition identity must remain withheld from the judge when required.",
    )

    severity = {
        "fail": 3,
        "insufficient-evidence": 2,
        "pass": 1,
        "not-applicable": 0,
    }
    all_gates: list[dict[str, Any]] = []
    for dimension in dimensions.values():
        gates = dimension["gates"]
        all_gates.extend(gates)
        if gates:
            dimension["status"] = max(
                (gate["status"] for gate in gates),
                key=lambda status: severity[status],
            )
    hard_gates = [gate for gate in all_gates if gate["hard"]]
    if any(gate["status"] == "fail" for gate in hard_gates):
        verdict = "rejected"
    elif any(gate["status"] == "insufficient-evidence" for gate in hard_gates):
        verdict = "insufficient-evidence"
    else:
        verdict = "approved"
    trigger_gate_scope: dict[str, Any] = (
        dict(discovery_input_comparison)
        if discovery_input_comparison is not None
        else {
            "canonical_fields": ["name", "description"],
            "changed": None,
            "changed_fields": None,
        }
    )
    trigger_gate_scope["trigger_gate_mode"] = (
        "observational" if trigger_gate_scope.get("changed") is False else "blocking"
    )
    return {
        "verdict": verdict,
        "approved": verdict == "approved",
        "hard_failure": any(gate["hard"] and gate["status"] == "fail" for gate in all_gates),
        "hard_blocked": any(gate["hard"] and gate["status"] != "pass" for gate in all_gates),
        "policy": {
            "status": "configured" if policy is not None else "missing",
            "effective": effective_policy.as_dict(),
        },
        "trigger_gate_scope": trigger_gate_scope,
        "dimensions": dimensions,
        "no_aggregate_override": True,
    }


def default_evaluation_conditions(skill_dir: Path) -> tuple[EvaluationCondition, ...]:
    """Return the ordered current-versus-baseline condition pair."""
    runtime_skill_dir = skill_dir.resolve()
    installation_name = runtime_skill_dir.name
    return (
        EvaluationCondition(
            id="skill",
            runtime_skill_dir=runtime_skill_dir,
            runtime_digest_sha256=stable_digest(
                runtime_skill_dir,
                exclude=RUNTIME_EXCLUDED_NAMES,
            ),
            installation_name=installation_name,
            display_label="Skill",
        ),
        EvaluationCondition(
            id="baseline",
            runtime_skill_dir=None,
            runtime_digest_sha256=None,
            installation_name=installation_name,
            display_label="Baseline",
        ),
    )


def candidate_evaluation_conditions(
    skill_dir: Path,
    candidate_dir: Path,
) -> tuple[EvaluationCondition, ...]:
    """Return current, baseline, and candidate conditions for one logical skill."""
    runtime_skill_dir = skill_dir.resolve()
    candidate_skill_dir = candidate_dir.resolve()
    installation_name = runtime_skill_dir.name
    return (
        EvaluationCondition(
            id="skill",
            runtime_skill_dir=runtime_skill_dir,
            runtime_digest_sha256=stable_digest(
                runtime_skill_dir,
                exclude=RUNTIME_EXCLUDED_NAMES,
            ),
            installation_name=installation_name,
            display_label="Current",
        ),
        EvaluationCondition(
            id="baseline",
            runtime_skill_dir=None,
            runtime_digest_sha256=None,
            installation_name=installation_name,
            display_label="Baseline",
        ),
        EvaluationCondition(
            id="candidate",
            runtime_skill_dir=candidate_skill_dir,
            runtime_digest_sha256=stable_digest(
                candidate_skill_dir,
                exclude=RUNTIME_EXCLUDED_NAMES,
            ),
            installation_name=installation_name,
            display_label="Candidate",
        ),
    )


def validate_candidate_separation(skill_dir: Path, candidate_dir: Path) -> None:
    """Reject nested packages whose runtime trees would contaminate one another."""
    current = skill_dir.resolve()
    candidate = candidate_dir.resolve()
    if current == candidate:
        return
    if current in candidate.parents or candidate in current.parents:
        raise EvalError(
            f"Candidate and current skill packages must not be nested: {candidate} and {current}"
        )


def resolve_candidate_skill(repo_root: Path, selector: Path, logical_name: str) -> Path:
    """Resolve and validate a publishable candidate for the selected logical skill."""
    supplied = selector.expanduser()
    candidate = supplied if supplied.is_absolute() else repo_root.resolve() / supplied
    if candidate.is_symlink():
        raise EvalError(f"Candidate skill directory may not be a symlink: {candidate}")
    candidate = candidate.resolve()
    if not candidate.is_dir():
        raise EvalError(f"Candidate skill directory does not exist: {candidate}")

    skill_md = candidate / "SKILL.md"
    if skill_md.is_symlink():
        raise EvalError(f"Candidate SKILL.md may not be a symlink: {skill_md}")
    if not skill_md.is_file():
        raise EvalError(f"Candidate is not a publishable skill package: missing {skill_md}")
    try:
        text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EvalError(f"Candidate SKILL.md must be UTF-8: {skill_md}") from exc

    # Reuse the repository's canonical, dependency-free YAML subset parser so
    # candidate packages obey the same publishable metadata contract.
    import validate_repo

    payload, _body = _parse_skill_document(text, skill_md, source="Candidate")

    extra_keys = sorted(set(payload) - validate_repo.ALLOWED_FRONTMATTER_KEYS)
    if extra_keys:
        raise EvalError(
            "Candidate SKILL.md has unsupported canonical frontmatter keys: "
            + ", ".join(extra_keys)
        )
    name_value = payload.get("name", "")
    name = name_value.strip() if isinstance(name_value, str) else ""
    if not name or not validate_repo.NAME_RE.fullmatch(name):
        raise EvalError(f"Candidate SKILL.md has an invalid name: {name!r}")
    if name != logical_name:
        raise EvalError(
            f"Candidate logical skill identity mismatch: expected {logical_name!r}, found {name!r}"
        )
    description_value = payload.get("description", "")
    description = description_value.strip() if isinstance(description_value, str) else ""
    if not description:
        raise EvalError("Candidate SKILL.md is missing a non-empty description")
    if len(description) > 1024:
        raise EvalError("Candidate SKILL.md description exceeds 1024 characters")

    for file_path in candidate.rglob("*"):
        relative = file_path.relative_to(candidate)
        if (
            not file_path.is_file()
            or file_path.is_symlink()
            or any(part in RUNTIME_EXCLUDED_NAMES for part in relative.parts)
        ):
            continue
        try:
            file_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in (
            *validate_repo.HARD_CODED_INSTALL_ROOTS,
            *validate_repo.FORBIDDEN_DISCOVERY_PATTERNS,
        ):
            if pattern in file_text:
                raise EvalError(
                    f"Candidate package is not portable: {file_path} contains {pattern!r}"
                )
        parent_ref = validate_repo.PARENT_PATH_RE.search(file_text)
        if parent_ref is not None:
            raise EvalError(
                "Candidate package is not portable: "
                f"{file_path} contains parent path {parent_ref.group(1)!r}"
            )

    for token in validate_repo.iter_inline_code_tokens(text):
        if not validate_repo.is_explicit_skill_local_path(token):
            continue
        local_path = (candidate / token).resolve()
        try:
            local_path.relative_to(candidate)
        except ValueError as exc:
            raise EvalError(f"Candidate SKILL.md path escapes the package: `{token}`") from exc
        if not local_path.exists():
            raise EvalError(f"Candidate SKILL.md references a missing local path: `{token}`")

    with tempfile.TemporaryDirectory(prefix="skill-eval-candidate-validation-") as temp_dir:
        runtime_skill_copy(candidate, Path(temp_dir) / logical_name)
    return candidate


def snapshot_candidate_skill(
    candidate_dir: Path,
    destination: Path,
    logical_name: str,
) -> Path:
    """Create and validate the immutable candidate runtime used for one evaluation."""
    runtime_skill_copy(candidate_dir, destination)
    return resolve_candidate_skill(destination.parent, destination, logical_name)


def runtime_skill_copy(skill_dir: Path, destination: Path) -> None:
    """Copy publishable runtime content without repository-generated files."""
    symlinks: list[Path] = []
    for path in skill_dir.rglob("*"):
        relative = path.relative_to(skill_dir)
        if any(part in RUNTIME_EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.is_symlink():
            symlinks.append(relative)
    symlinks.sort()
    if symlinks:
        display = ", ".join(path.as_posix() for path in symlinks)
        raise EvalError(f"Skill runtime content may not contain symlinks: {display}")

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return set(RUNTIME_EXCLUDED_NAMES.intersection(names))

    shutil.copytree(skill_dir, destination, ignore=ignore)


def skill_instructions(skill_dir: Path) -> str:
    """Return the canonical instructions installed into an evaluator runtime."""
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_symlink():
        raise EvalError(f"Skill runtime content may not contain symlinks: {skill_md.name}")
    return skill_md.read_text(encoding="utf-8")


_EXPECTED_SECTION = re.compile(
    r"^(?:"
    r"#{1,6}\s+(?:expected(?:\s+behavior)?|checks?|grading|assertions?)\b"
    r"|(?:expected(?:\s+behavior)?|checks?|grading|assertions?)\s*:"
    r")",
    flags=re.IGNORECASE,
)


def _sanitized_recipe(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        if _EXPECTED_SECTION.match(line.strip()):
            break
        kept.append(line)
    return "\n".join(kept).rstrip() + "\n"


def _safe_ref(ref: str) -> Path:
    candidate = Path(ref)
    parts = candidate.parts
    exposes_eval_ground_truth = not parts or parts[0] == "evals.json"
    selects_fixture_root = parts == ("fixtures",)
    if (
        candidate.is_absolute()
        or ".." in parts
        or exposes_eval_ground_truth
        or selects_fixture_root
    ):
        raise EvalError(
            "Fixture path must be eval-relative, may not traverse parents, and may not "
            f"select eval ground truth or the broad fixture root: {ref}"
        )
    return candidate


def _fixture_target(relative: Path) -> Path:
    parts = relative.parts
    if parts and parts[0] == "fixtures":
        return Path(*parts[2:] if len(parts) >= 3 else parts[1:])
    return relative


def _copy_fixture_file(source: Path, target: Path) -> None:
    if source.is_symlink():
        raise EvalError(f"Fixture sources may not be symlinks: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise EvalError(f"Fixture collision at workspace path: {target}")
    shutil.copy2(source, target)


def materialize_fixtures(
    eval_dir: Path,
    fixture_refs: tuple[str, ...],
    workspace: Path,
    *,
    allow_setup_scripts: bool,
) -> tuple[list[dict[str, Any]], list[Path]]:
    """Copy fixtures into a workspace and return deferred trusted setup scripts."""
    records: list[dict[str, Any]] = []
    setup_scripts: list[Path] = []
    scenario_dir = workspace / ".eval" / "fixtures"

    for ref in fixture_refs:
        safe = _safe_ref(ref)
        candidates = [eval_dir / safe]
        if len(safe.parts) == 1:
            candidates.extend(
                [
                    eval_dir / "fixtures" / safe,
                    eval_dir / f"{safe}.md",
                ]
            )
        source = next((candidate for candidate in candidates if candidate.exists()), None)
        if source is None:
            records.append(
                {
                    "reference": ref,
                    "status": "missing",
                    "mode": "unresolved",
                    "message": "No matching fixture file or directory was found",
                }
            )
            continue
        if source.is_symlink():
            raise EvalError(f"Fixture sources may not be symlinks: {source}")

        if source.is_file() and source.suffix.lower() == ".md" and source.parent == eval_dir:
            scenario_dir.mkdir(parents=True, exist_ok=True)
            destination = scenario_dir / source.name
            destination.write_text(
                _sanitized_recipe(source.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
            records.append(
                {
                    "reference": ref,
                    "status": "ready",
                    "mode": "description_only",
                    "source": str(source),
                    "target": str(destination.relative_to(workspace)),
                    "message": "Scenario recipe materialized; expected-behavior sections withheld",
                }
            )
            continue

        copied: list[str] = []
        scripts: list[Path] = []
        if source.is_dir():
            for item in sorted(source.rglob("*")):
                if not item.is_file():
                    continue
                relative = item.relative_to(source)
                if relative == Path("setup.sh"):
                    scripts.append(item)
                    continue
                destination = workspace / relative
                _copy_fixture_file(item, destination)
                copied.append(str(relative))
        else:
            relative_to_eval = source.relative_to(eval_dir)
            destination_rel = _fixture_target(relative_to_eval)
            destination = workspace / destination_rel
            _copy_fixture_file(source, destination)
            copied.append(str(destination_rel))

        if scripts and allow_setup_scripts:
            setup_scripts.extend(scripts)
        records.append(
            {
                "reference": ref,
                "status": "ready" if not scripts or allow_setup_scripts else "degraded",
                "mode": "executable" if scripts and allow_setup_scripts else "files",
                "source": str(source),
                "copied": copied,
                "setup_scripts": [str(path) for path in scripts],
                "message": (
                    "Fixture files copied and setup deferred"
                    if scripts and allow_setup_scripts
                    else "Fixture files copied"
                    if not scripts
                    else "Fixture setup script was not allowed"
                ),
            }
        )
    return records, setup_scripts


def initialize_fixture_repository(workspace: Path) -> dict[str, Any]:
    """Create a deterministic baseline Git repository when a fixture did not provide one."""
    if (workspace / ".git").exists():
        return {"ok": True, "created": False, "reason": "fixture supplied .git"}
    commands = [
        ["git", "init", "-q", "-b", "eval-base"],
        ["git", "config", "user.name", "Skill Eval"],
        ["git", "config", "user.email", "skill-eval@invalid"],
        ["git", "add", "-A"],
    ]
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return {
                "ok": False,
                "created": False,
                "reason": f"{' '.join(command)} failed: {completed.stderr.strip()}",
            }
    commit = subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "eval: baseline fixture"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        return {
            "ok": False,
            "created": False,
            "reason": f"git commit failed: {commit.stderr.strip()}",
        }
    return {"ok": True, "created": True, "branch": "eval-base"}


def run_fixture_setups(
    scripts: list[Path],
    workspace: Path,
    skill_dir: Path,
    *,
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for script in scripts:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(workspace),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "EVAL_WORKSPACE": str(workspace),
            "EVAL_SKILL_DIR": str(skill_dir),
        }
        try:
            completed = subprocess.run(
                ["bash", str(script)],
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            results.append(
                {
                    "script": str(script),
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout[-4000:],
                    "stderr": completed.stderr[-4000:],
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "script": str(script),
                    "exit_code": None,
                    "stdout": "",
                    "stderr": f"Timed out after {timeout_seconds}s",
                }
            )
    return results


def snapshot_workspace(workspace: Path, *, preview_bytes: int = 12_000) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.is_symlink():
            continue
        relative = str(path.relative_to(workspace))
        data = path.read_bytes()
        record: dict[str, Any] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }
        try:
            text = data.decode("utf-8")
            if len(data) <= preview_bytes:
                record["text"] = text
            else:
                prefix_bytes = preview_bytes // 2
                suffix_bytes = preview_bytes - prefix_bytes
                prefix = data[:prefix_bytes].decode("utf-8", errors="ignore")
                suffix = data[-suffix_bytes:].decode("utf-8", errors="ignore")
                omitted = len(data) - prefix_bytes - suffix_bytes
                record["text"] = f"{prefix}\n... <{omitted} bytes omitted> ...\n{suffix}"
                record["text_truncated"] = True
        except UnicodeDecodeError:
            pass
        files[relative] = record
    return {"files": files}


def workspace_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_files = before["files"]
    after_files = after["files"]
    created = sorted(set(after_files) - set(before_files))
    deleted = sorted(set(before_files) - set(after_files))
    modified = sorted(
        path
        for path in set(before_files).intersection(after_files)
        if before_files[path]["sha256"] != after_files[path]["sha256"]
    )
    return {
        "created": [{"path": path, **after_files[path]} for path in created],
        "modified": [{"path": path, **after_files[path]} for path in modified],
        "deleted": [{"path": path, **before_files[path]} for path in deleted],
    }


def git_observations(workspace: Path) -> dict[str, Any]:
    if not (workspace / ".git").exists():
        return {"available": False}
    observations: dict[str, Any] = {"available": True}
    commands = {
        "status": ["git", "status", "--short", "--branch"],
        "log": ["git", "log", "--oneline", "--decorate", "-10"],
        "head_commit": [
            "git",
            "show",
            "--stat",
            "--name-status",
            "--format=fuller",
            "--no-renames",
            "HEAD",
        ],
        "diff_stat": ["git", "diff", "--stat", "HEAD"],
        "staged_diff_stat": ["git", "diff", "--cached", "--stat", "HEAD"],
    }
    for key, command in commands.items():
        completed = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        observations[key] = (completed.stdout + completed.stderr)[-8000:].strip()
        observations[f"{key}_exit_code"] = completed.returncode
    return observations


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize_trigger_results(
    cases: tuple[TriggerCase, ...],
    runs: list[dict[str, Any]],
    *,
    threshold: float,
) -> dict[str, Any]:
    by_case: list[dict[str, Any]] = []
    tp = fp = tn = fn = 0
    successful_runs = 0
    total_runs = 0
    for case in cases:
        case_runs = [run for run in runs if run["case_id"] == case.id]
        completed = [run for run in case_runs if run["status"] == "completed"]
        activations = sum(bool(run.get("activated")) for run in completed)
        rate = _rate(activations, len(completed))
        predicted = rate is not None and rate >= threshold
        passed = predicted == case.should_trigger if rate is not None else False
        successful_runs += sum(
            bool(run.get("activated")) == case.should_trigger for run in completed
        )
        total_runs += len(completed)
        if rate is not None:
            if case.should_trigger and predicted:
                tp += 1
            elif case.should_trigger:
                fn += 1
            elif predicted:
                fp += 1
            else:
                tn += 1
        by_case.append(
            {
                "id": case.id,
                "query": case.query,
                "expected": case.should_trigger,
                "activation_rate": rate,
                "activation_interval_95": wilson_interval(activations, len(completed)),
                "completed_runs": len(completed),
                "total_runs": len(case_runs),
                "predicted": predicted if rate is not None else None,
                "passed": passed,
            }
        )

    positive_total = sum(case.should_trigger for case in cases)
    negative_total = sum(not case.should_trigger for case in cases)
    recall = _rate(tp, positive_total)
    specificity = _rate(tn, negative_total)
    precision = _rate(tp, tp + fp)
    accuracy = _rate(tp + tn, len(cases))
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    balanced = (
        (recall + specificity) / 2
        if recall is not None and specificity is not None
        else recall
        if recall is not None
        else specificity
    )
    return {
        "threshold": threshold,
        "confusion_matrix": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "unscored": len(cases) - tp - fp - tn - fn,
        },
        "case_accuracy": accuracy,
        "case_accuracy_interval_95": wilson_interval(tp + tn, len(cases)),
        "evidence_coverage": _rate(tp + fp + tn + fn, len(cases)),
        "run_accuracy": _rate(successful_runs, total_runs),
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "balanced_accuracy": balanced,
        "cases": by_case,
        "run_errors": sum(run["status"] != "completed" for run in runs),
    }


def _grade_counts(
    grades: Iterable[dict[str, Any]],
) -> dict[str, int | float | list[float] | None]:
    items = list(grades)
    passed = sum(item.get("passed") is True for item in items)
    failed = sum(item.get("passed") is False for item in items)
    unknown = len(items) - passed - failed
    known = passed + failed
    return {
        "total": len(items),
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "pass_rate": _rate(passed, len(items)),
        "known_pass_rate": _rate(passed, known),
        "evidence_coverage": _rate(known, len(items)),
        "pass_interval_95": wilson_interval(passed, len(items)),
    }


def summarize_behavior_results(
    results: list[dict[str, Any]],
    conditions: tuple[EvaluationCondition, ...],
) -> dict[str, Any]:
    condition_ids = tuple(condition.id for condition in conditions)
    if len(conditions) not in {2, 3} or len(set(condition_ids)) != len(condition_ids):
        raise EvalError("behavior summaries require two or three distinct conditions")
    reserved_ids = sorted(set(condition_ids) & BEHAVIOR_SUMMARY_RESERVED_KEYS)
    if reserved_ids:
        raise EvalError(
            "condition id(s) collide with reserved behavior summary keys: "
            + ", ".join(reserved_ids)
        )
    primary, comparison = conditions[:2]
    grades_by_condition: dict[str, list[dict[str, Any]]] = {
        condition.id: [] for condition in conditions
    }
    case_passes = {condition.id: 0 for condition in conditions}
    graded_cases = 0
    case_summaries: list[dict[str, Any]] = []

    for result in results:
        result_grades = result.get("grades", {})
        for condition in conditions:
            grades_by_condition[condition.id].extend(result_grades.get(condition.id, []))
        if any(result_grades.get(condition.id, []) for condition in conditions):
            graded_cases += 1
        condition_case_passes = {
            condition.id: bool(result_grades.get(condition.id, []))
            and all(item.get("passed") is True for item in result_grades.get(condition.id, []))
            for condition in conditions
        }
        for condition in conditions:
            case_passes[condition.id] += condition_case_passes[condition.id]
        case_summaries.append(
            {
                "id": result["case_id"],
                "repeat": result["repeat"],
                **{
                    f"{condition.id}_case_pass": condition_case_passes[condition.id]
                    for condition in conditions
                },
                **{
                    f"{condition.id}_status": result[f"{condition.id}_run"]["status"]
                    for condition in conditions
                },
                **{
                    f"{condition.id}_activated": result[f"{condition.id}_run"].get("activated")
                    for condition in conditions
                },
                "fixture_fidelity": result.get("fixture_fidelity"),
                "judge_status": result.get("judge", {}).get("status"),
            }
        )

    counts = {
        condition.id: _grade_counts(grades_by_condition[condition.id]) for condition in conditions
    }

    def compare(
        left: EvaluationCondition,
        right: EvaluationCondition,
    ) -> dict[str, Any]:
        left_rate = counts[left.id]["pass_rate"]
        right_rate = counts[right.id]["pass_rate"]
        lift = (
            left_rate - right_rate
            if isinstance(left_rate, float) and isinstance(right_rate, float)
            else None
        )
        left_wins = right_wins = ties = unknown = 0
        for result in results:
            left_grades = result.get("grades", {}).get(left.id, [])
            right_grades = result.get("grades", {}).get(right.id, [])
            for left_item, right_item in zip(left_grades, right_grades, strict=False):
                pair = (left_item.get("passed"), right_item.get("passed"))
                if pair == (True, False):
                    left_wins += 1
                elif pair == (False, True):
                    right_wins += 1
                elif None in pair:
                    unknown += 1
                else:
                    ties += 1
        return {
            "left_condition": left.id,
            "left_label": left.display_label,
            "right_condition": right.id,
            "right_label": right.display_label,
            "absolute_lift": lift,
            "lift_percentage_points": lift * 100 if lift is not None else None,
            "paired_checks": {
                "left_wins": left_wins,
                "right_wins": right_wins,
                "ties": ties,
                "unknown": unknown,
            },
        }

    current_vs_baseline = compare(primary, comparison)

    runs_by_condition = {
        condition.id: [result[f"{condition.id}_run"] for result in results]
        for condition in conditions
    }

    def efficiency(runs: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [run for run in runs if run["status"] == "completed"]
        durations = [float(run["duration_seconds"]) for run in completed]

        def usage_values(key: str) -> list[int] | None:
            values: list[int] = []
            for run in completed:
                usage = run.get("usage")
                if not isinstance(usage, dict):
                    return None
                value = usage.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    return None
                values.append(value)
            return values or None

        input_values = usage_values("input_tokens")
        output_values = usage_values("output_tokens")
        total_values = (
            [
                input_value + output_value
                for input_value, output_value in zip(input_values, output_values, strict=True)
            ]
            if input_values is not None and output_values is not None
            else None
        )
        return {
            "completed_runs": len(completed),
            "failed_runs": len(runs) - len(completed),
            "errors": len(runs) - len(completed),
            "median_duration_seconds": statistics.median(durations) if durations else None,
            "input_tokens": sum(input_values) if input_values is not None else None,
            "output_tokens": sum(output_values) if output_values is not None else None,
            "total_tokens": sum(total_values) if total_values is not None else None,
            "median_tokens": statistics.median(total_values) if total_values is not None else None,
            "tool_calls": sum(int(run.get("tool_calls", 0)) for run in completed),
        }

    activation_completed = [
        run for run in runs_by_condition[primary.id] if run["status"] == "completed"
    ]
    summary = {
        **counts,
        "absolute_lift": current_vs_baseline["absolute_lift"],
        "lift_percentage_points": current_vs_baseline["lift_percentage_points"],
        "paired_checks": {
            "skill_wins": current_vs_baseline["paired_checks"]["left_wins"],
            "regressions": current_vs_baseline["paired_checks"]["right_wins"],
            "ties": current_vs_baseline["paired_checks"]["ties"],
            "unknown": current_vs_baseline["paired_checks"]["unknown"],
        },
        "case_pass_rate": {
            **{
                condition.id: _rate(case_passes[condition.id], graded_cases)
                for condition in conditions
            },
            "graded_cases": graded_cases,
        },
        "behavior_activation_rate": _rate(
            sum(bool(run.get("activated")) for run in activation_completed),
            len(activation_completed),
        ),
        "efficiency": {
            condition.id: efficiency(runs_by_condition[condition.id]) for condition in conditions
        },
        "cases": case_summaries,
    }
    if len(conditions) == 3:
        candidate = conditions[2]
        summary["comparisons"] = {
            "current_vs_baseline": current_vs_baseline,
            "candidate_vs_baseline": compare(candidate, comparison),
            "candidate_vs_current": compare(candidate, primary),
        }
    return summary


def efficacy_profile(
    trigger_summary: dict[str, Any] | None,
    behavior_summary: dict[str, Any] | None,
    conditions: tuple[EvaluationCondition, ...],
) -> dict[str, Any]:
    if not conditions:
        raise EvalError("efficacy profiles require at least one condition")
    primary = conditions[0]
    activation = trigger_summary.get("balanced_accuracy") if trigger_summary is not None else None
    execution = (
        behavior_summary.get(primary.id, {}).get("pass_rate")
        if behavior_summary is not None
        else None
    )
    lift = behavior_summary.get("absolute_lift") if behavior_summary is not None else None
    coverage = (
        behavior_summary.get(primary.id, {}).get("evidence_coverage")
        if behavior_summary is not None
        else None
    )
    components = [(activation, 0.4), (execution, 0.6)]
    available = [(value, weight) for value, weight in components if isinstance(value, float)]
    absolute = (
        sum(value * weight for value, weight in available)
        / sum(weight for _value, weight in available)
        if available
        else None
    )

    if execution is None:
        verdict = "activation-only"
    elif lift is None:
        verdict = "uncompared"
    elif lift < -0.05:
        verdict = "regressive"
    elif lift >= 0.15 and execution >= 0.7:
        verdict = "effective"
    elif lift > 0 and execution >= 0.5:
        verdict = "promising"
    elif lift == 0:
        verdict = "no-measurable-lift"
    else:
        verdict = "mixed"
    return {
        "absolute_efficacy": absolute,
        "absolute_efficacy_percent": absolute * 100 if absolute is not None else None,
        "activation_quality": activation,
        "execution_quality": execution,
        "incremental_lift": lift,
        "evidence_coverage": coverage,
        "verdict": verdict,
        "formula": (
            "40% trigger balanced accuracy + 60% "
            f"{primary.display_label.lower()} check pass rate; available components are renormalized"
        ),
        "note": "Incremental lift is reported separately so a strong general model is not mistaken for skill value.",
    }


def json_dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
