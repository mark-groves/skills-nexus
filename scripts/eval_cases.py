"""Thin evals.json catalog, skill resolve, and optional companion loaders."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

RUNTIME_EXCLUDED_NAMES = frozenset({"evals", "working", "__pycache__", ".git"})
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
CASE_GROUP_SCHEMA_VERSION = 1
ROUTINE_SCREEN_SCHEMA_VERSION = 1
COMPONENT_SCHEMA_VERSION = 1
MAX_CASE_GROUPS = 32
MAX_CASES_PER_KIND = 512
MAX_COMPONENTS = 128
SAFE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
HEADING_RE = re.compile(r"^(#{2,6})[ \t]+(.+?)[ \t]*$")
BOUNDARY_HEADING_RE = re.compile(r"^[ ]{0,3}(#{1,6})(?:[ \t]+.*)?$")
SETEXT_RE = re.compile(r"^[ \t]*(?:=+|-+)[ \t]*$")
FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,}).*$")


class EvalError(RuntimeError):
    """Raised for a user-actionable catalog or companion contract error."""


def _runtime_package_files(path: Path, *, exclude: Iterable[str] = ()) -> tuple[Path, ...]:
    excluded = set(exclude)
    return tuple(
        item
        for item in sorted(path.rglob("*"), key=lambda entry: entry.as_posix())
        if item.is_file()
        and not item.is_symlink()
        and not any(part in excluded for part in item.relative_to(path).parts)
    )


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvalError(f"Missing {label}: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise EvalError(f"Unable to read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvalError(f"Invalid JSON in {label} {path}: {exc}") from exc


def _object(value: object, *, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvalError(f"{location} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, location: str) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    details = []
    if missing:
        details.append("missing " + ", ".join(missing))
    if extra:
        details.append("unexpected " + ", ".join(extra))
    if details:
        raise EvalError(f"{location} has invalid keys ({'; '.join(details)})")


def _safe_id(value: object, *, location: str) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise EvalError(
            f"{location} must be a lowercase kebab-case identifier between 1 and 64 characters"
        )
    return value


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
    """Return publishable skill packages from the repository.

    Production layout is Agent Plugin bundles under ``plugins/<bundle>/skills/``.
    A flat ``skills/<name>/`` tree remains supported for isolated test fixtures.
    """
    repo_root = repo_root.resolve()
    plugins_root = repo_root / "plugins"
    if plugins_root.is_dir() and not plugins_root.is_symlink():
        plugin_skills = tuple(
            sorted(
                (
                    path.parent.resolve()
                    for path in plugins_root.glob("*/skills/*/SKILL.md")
                    if path.is_file()
                    and not path.is_symlink()
                    and not any(
                        part.startswith(".") for part in path.relative_to(plugins_root).parts
                    )
                ),
                key=lambda path: str(path),
            )
        )
        if plugin_skills:
            return plugin_skills

    skills_root = repo_root / "skills"
    if not skills_root.is_dir() or skills_root.is_symlink():
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

    matches = [path for path in discover_repository_skills(repo_root) if path.name == selector]
    if not matches:
        raise EvalError(
            f"No skill matches {selector!r}. Use a short name such as 'commit', "
            "a repository path such as 'plugins/git-workflow/skills/commit', "
            "or a skill directory path."
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


def runtime_skill_copy(skill_dir: Path, destination: Path) -> None:
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


@dataclass(frozen=True, order=True)
class CaseGroup:
    id: str
    kind: str
    trigger_cases: tuple[str, ...]
    behavior_cases: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "trigger_cases": list(self.trigger_cases),
            "behavior_cases": list(self.behavior_cases),
        }


@dataclass(frozen=True)
class RoutineScreenContract:
    schema_version: int
    trigger_cases: tuple[str, ...]
    behavior_cases: tuple[str, ...]
    digest_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trigger_cases": list(self.trigger_cases),
            "behavior_cases": list(self.behavior_cases),
        }


def _case_ids(
    value: object,
    *,
    location: str,
    known: set[str],
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_CASES_PER_KIND:
        raise EvalError(
            f"{location} must be a list containing at most {MAX_CASES_PER_KIND} case ids"
        )
    result: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise EvalError(f"{location}[{index}] must be a string or integer case id")
        case_id = str(item).strip()
        if not case_id or case_id in {".", ".."} or "/" in case_id or "\\" in case_id:
            raise EvalError(f"{location}[{index}] must be a safe non-empty case id")
        result.append(case_id)
    duplicates = sorted(case_id for case_id in set(result) if result.count(case_id) > 1)
    if duplicates:
        raise EvalError(f"{location} contains duplicate case id(s): {', '.join(duplicates)}")
    unknown = sorted(set(result) - known)
    if unknown:
        raise EvalError(f"{location} contains unknown case id(s): {', '.join(unknown)}")
    return tuple(result)


def load_case_groups(path: Path | None, spec: EvalSpec) -> tuple[CaseGroup, ...]:
    all_trigger = tuple(case.id for case in spec.trigger_cases)
    all_behavior = tuple(case.id for case in spec.behavior_cases)
    if path is None:
        return (
            CaseGroup(
                id="development",
                kind="development",
                trigger_cases=all_trigger,
                behavior_cases=all_behavior,
            ),
        )

    payload = _object(_load_json(path, label="case group definition"), location=str(path))
    _exact_keys(payload, {"schema_version", "groups"}, location=str(path))
    if payload["schema_version"] != CASE_GROUP_SCHEMA_VERSION:
        raise EvalError(
            f"{path}.schema_version must be {CASE_GROUP_SCHEMA_VERSION}, "
            f"found {payload['schema_version']!r}"
        )
    supplied_groups = payload["groups"]
    if (
        not isinstance(supplied_groups, list)
        or not supplied_groups
        or len(supplied_groups) > MAX_CASE_GROUPS
    ):
        raise EvalError(f"{path}.groups must contain between 1 and {MAX_CASE_GROUPS} groups")

    groups: list[CaseGroup] = []
    seen_group_ids: set[str] = set()
    assigned_trigger: set[str] = set()
    assigned_behavior: set[str] = set()
    trigger_known = set(all_trigger)
    behavior_known = set(all_behavior)
    for index, supplied in enumerate(supplied_groups):
        location = f"{path}.groups[{index}]"
        item = _object(supplied, location=location)
        _exact_keys(
            item,
            {"id", "kind", "trigger_cases", "behavior_cases"},
            location=location,
        )
        group_id = _safe_id(item["id"], location=f"{location}.id")
        if group_id in seen_group_ids:
            raise EvalError(f"Duplicate case group id in {path}: {group_id}")
        seen_group_ids.add(group_id)
        kind = item["kind"]
        if kind not in {"development", "held-back"}:
            raise EvalError(f"{location}.kind must be 'development' or 'held-back'")
        trigger_cases = _case_ids(
            item["trigger_cases"],
            location=f"{location}.trigger_cases",
            known=trigger_known,
        )
        behavior_cases = _case_ids(
            item["behavior_cases"],
            location=f"{location}.behavior_cases",
            known=behavior_known,
        )
        if not trigger_cases and not behavior_cases:
            raise EvalError(f"{location} must identify at least one trigger or behavior case")
        duplicate_trigger = sorted(set(trigger_cases) & assigned_trigger)
        duplicate_behavior = sorted(set(behavior_cases) & assigned_behavior)
        if duplicate_trigger or duplicate_behavior:
            detail = []
            if duplicate_trigger:
                detail.append("trigger " + ", ".join(duplicate_trigger))
            if duplicate_behavior:
                detail.append("behavior " + ", ".join(duplicate_behavior))
            raise EvalError(f"{location} overlaps an earlier group ({'; '.join(detail)})")
        assigned_trigger.update(trigger_cases)
        assigned_behavior.update(behavior_cases)
        groups.append(CaseGroup(group_id, kind, trigger_cases, behavior_cases))

    missing_trigger = sorted(trigger_known - assigned_trigger)
    missing_behavior = sorted(behavior_known - assigned_behavior)
    if missing_trigger or missing_behavior:
        detail = []
        if missing_trigger:
            detail.append("trigger " + ", ".join(missing_trigger))
        if missing_behavior:
            detail.append("behavior " + ", ".join(missing_behavior))
        raise EvalError(
            f"{path}.groups must assign every eval case exactly once; missing " + "; ".join(detail)
        )
    return tuple(groups)


def load_routine_screen_contract(
    path: Path,
    spec: EvalSpec,
    groups: tuple[CaseGroup, ...],
) -> RoutineScreenContract:
    if path.is_symlink():
        raise EvalError(f"Routine screen contract may not be a symlink: {path}")
    payload = _object(_load_json(path, label="routine screen contract"), location=str(path))
    _exact_keys(
        payload,
        {"schema_version", "trigger_cases", "behavior_cases"},
        location=str(path),
    )
    if payload["schema_version"] != ROUTINE_SCREEN_SCHEMA_VERSION:
        raise EvalError(
            f"{path}.schema_version must be {ROUTINE_SCREEN_SCHEMA_VERSION}, "
            f"found {payload['schema_version']!r}"
        )
    trigger_known = {case.id for case in spec.trigger_cases}
    behavior_known = {case.id for case in spec.behavior_cases}
    trigger_cases = _case_ids(
        payload["trigger_cases"],
        location=f"{path}.trigger_cases",
        known=trigger_known,
    )
    behavior_cases = _case_ids(
        payload["behavior_cases"],
        location=f"{path}.behavior_cases",
        known=behavior_known,
    )
    if len(trigger_cases) != 2:
        raise EvalError(f"{path}.trigger_cases must contain exactly two case ids")
    if not 2 <= len(behavior_cases) <= 3:
        raise EvalError(f"{path}.behavior_cases must contain two or three case ids")

    trigger_by_id = {case.id: case for case in spec.trigger_cases}
    trigger_polarities = {trigger_by_id[case_id].should_trigger for case_id in trigger_cases}
    if trigger_polarities != {True, False}:
        raise EvalError(
            f"{path}.trigger_cases must contain one positive and one near-miss negative case"
        )

    development_trigger = {
        case_id
        for group in groups
        if group.kind == "development"
        for case_id in group.trigger_cases
    }
    development_behavior = {
        case_id
        for group in groups
        if group.kind == "development"
        for case_id in group.behavior_cases
    }
    nondevelopment_trigger = sorted(set(trigger_cases) - development_trigger)
    nondevelopment_behavior = sorted(set(behavior_cases) - development_behavior)
    if nondevelopment_trigger or nondevelopment_behavior:
        details = []
        if nondevelopment_trigger:
            details.append("trigger " + ", ".join(nondevelopment_trigger))
        if nondevelopment_behavior:
            details.append("behavior " + ", ".join(nondevelopment_behavior))
        raise EvalError(
            f"{path} may select development cases only; held-back cases are reserved "
            f"for full escalation ({'; '.join(details)})"
        )

    behavior_by_id = {case.id: case for case in spec.behavior_cases}
    if not any(
        check.gate == "hard"
        for case_id in behavior_cases
        for check in behavior_by_id[case_id].checks
    ):
        raise EvalError(f"{path}.behavior_cases must exercise at least one protected hard check")

    normalized = {
        "schema_version": ROUTINE_SCREEN_SCHEMA_VERSION,
        "trigger_cases": list(trigger_cases),
        "behavior_cases": list(behavior_cases),
    }
    return RoutineScreenContract(
        schema_version=ROUTINE_SCREEN_SCHEMA_VERSION,
        trigger_cases=trigger_cases,
        behavior_cases=behavior_cases,
        digest_sha256=canonical_digest(normalized),
    )


@dataclass(frozen=True)
class Component:
    id: str
    source: str
    heading: str
    class_name: str
    protected: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "heading": self.heading,
            "class": self.class_name,
            "protected": self.protected,
        }


@dataclass(frozen=True)
class SectionSpan:
    component: Component
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ComponentContract:
    schema_version: int
    components: tuple[Component, ...]
    digest_sha256: str
    spans: dict[str, SectionSpan]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "components": [component.as_dict() for component in self.components],
        }


def _source_path(skill_dir: Path, source: object, *, location: str) -> tuple[str, Path]:
    if not isinstance(source, str) or not source or "\\" in source:
        raise EvalError(f"{location} must be a non-empty POSIX relative path")
    relative = PurePosixPath(source)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise EvalError(f"{location} must stay within the runtime skill package")
    if relative.suffix.lower() not in {".md", ".markdown"}:
        raise EvalError(f"{location} must select a Markdown source file")
    excluded = sorted(set(relative.parts) & RUNTIME_EXCLUDED_NAMES)
    if excluded:
        raise EvalError(f"{location} selects runtime-excluded path name(s): {', '.join(excluded)}")
    unresolved = skill_dir
    for part in relative.parts:
        unresolved /= part
        if unresolved.is_symlink():
            raise EvalError(f"{location} must not traverse a runtime symlink: {source}")
    target = unresolved.resolve()
    try:
        target.relative_to(skill_dir.resolve())
    except ValueError as exc:
        raise EvalError(f"{location} escapes the runtime skill package") from exc
    if not target.is_file():
        raise EvalError(f"{location} must resolve to one regular runtime file: {source}")
    return relative.as_posix(), target


def _heading_level(line: str) -> int | None:
    match = BOUNDARY_HEADING_RE.fullmatch(line.rstrip("\r\n"))
    return len(match.group(1)) if match is not None else None


def _markdown_heading_levels(lines: list[str]) -> list[int | None]:
    levels: list[int | None] = []
    fence_character: str | None = None
    fence_length = 0
    frontmatter = bool(lines and lines[0].rstrip("\r\n") == "---")
    previous_content = False
    for index, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        if frontmatter:
            levels.append(None)
            previous_content = False
            if index > 0 and stripped == "---":
                frontmatter = False
            continue
        fence = FENCE_RE.fullmatch(stripped)
        if fence_character is None:
            if fence is not None:
                marker = fence.group(1)
                fence_character = marker[0]
                fence_length = len(marker)
                levels.append(None)
                previous_content = False
                continue
            if previous_content and SETEXT_RE.fullmatch(stripped) is not None:
                raise EvalError("Markdown component sources must not contain setext headings")
            levels.append(_heading_level(line))
            previous_content = bool(stripped.strip())
            continue
        closing = re.fullmatch(
            rf"[ ]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
            stripped,
        )
        if closing is not None:
            fence_character = None
            fence_length = 0
        levels.append(None)
        previous_content = False
    return levels


def _read_text_exact(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()
    except UnicodeDecodeError as exc:
        raise EvalError(f"Component source must be UTF-8: {path}") from exc


def _resolve_span(source: Path, component: Component) -> SectionSpan:
    text = _read_text_exact(source)
    lines = text.splitlines(keepends=True)
    heading_levels = _markdown_heading_levels(lines)
    matches = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\r\n") == component.heading and heading_levels[index] is not None
    ]
    if len(matches) != 1:
        raise EvalError(
            f"Component {component.id!r} heading must resolve exactly once in "
            f"{component.source}; found {len(matches)}"
        )
    start_line = matches[0]
    level = heading_levels[start_line]
    if (
        level is None
        or not 2 <= level <= 6
        or HEADING_RE.fullmatch(lines[start_line].rstrip("\r\n")) is None
    ):
        raise EvalError(
            f"Component {component.id!r} heading must be an exact level 2-6 ATX heading"
        )
    end_line = len(lines)
    for index in range(start_line + 1, len(lines)):
        next_level = heading_levels[index]
        if next_level is not None and next_level <= level:
            end_line = index
            break
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    start = offsets[start_line]
    end = offsets[end_line]
    if start == end:
        raise EvalError(f"Component {component.id!r} resolved to an empty section")
    return SectionSpan(component=component, start=start, end=end, text=text[start:end])


def load_component_contract(path: Path, skill_dir: Path) -> ComponentContract:
    if path.is_symlink():
        raise EvalError(f"Component metadata must not be a symlink: {path}")
    payload = _load_json(path, label="component metadata")
    if not isinstance(payload, dict):
        raise EvalError(f"Component metadata must be an object: {path}")
    _exact_keys(payload, {"schema_version", "components"}, location=str(path))
    if payload["schema_version"] != COMPONENT_SCHEMA_VERSION:
        raise EvalError(
            f"{path}.schema_version must be {COMPONENT_SCHEMA_VERSION}, "
            f"found {payload['schema_version']!r}"
        )
    supplied = payload["components"]
    if not isinstance(supplied, list) or not supplied or len(supplied) > MAX_COMPONENTS:
        raise EvalError(f"{path}.components must contain between 1 and {MAX_COMPONENTS} components")

    components: list[Component] = []
    spans: dict[str, SectionSpan] = {}
    seen_ids: set[str] = set()
    seen_selectors: set[tuple[str, str]] = set()
    for index, raw in enumerate(supplied):
        location = f"{path}.components[{index}]"
        if not isinstance(raw, dict):
            raise EvalError(f"{location} must be an object")
        _exact_keys(
            raw,
            {"id", "source", "heading", "class", "protected"},
            location=location,
        )
        component_id = _safe_id(raw["id"], location=f"{location}.id")
        if component_id in seen_ids:
            raise EvalError(f"Duplicate component id in {path}: {component_id}")
        seen_ids.add(component_id)
        source_name, source_path = _source_path(
            skill_dir,
            raw["source"],
            location=f"{location}.source",
        )
        heading = raw["heading"]
        if not isinstance(heading, str) or not heading or "\n" in heading or "\r" in heading:
            raise EvalError(f"{location}.heading must be one exact non-empty line")
        selector = (source_name, heading)
        if selector in seen_selectors:
            raise EvalError(f"Duplicate component selector in {path}: {source_name} {heading!r}")
        seen_selectors.add(selector)
        class_name = _safe_id(raw["class"], location=f"{location}.class")
        if not isinstance(raw["protected"], bool):
            raise EvalError(f"{location}.protected must be boolean")
        component = Component(
            id=component_id,
            source=source_name,
            heading=heading,
            class_name=class_name,
            protected=raw["protected"],
        )
        components.append(component)
        spans[component.id] = _resolve_span(source_path, component)

    by_source: dict[str, list[SectionSpan]] = {}
    for span in spans.values():
        by_source.setdefault(span.component.source, []).append(span)
    for source, source_spans in by_source.items():
        ordered = sorted(source_spans, key=lambda item: (item.start, item.end))
        for left, right in zip(ordered, ordered[1:], strict=False):
            if left.end > right.start:
                raise EvalError(
                    "Component selectors must not overlap or nest in "
                    f"{source}: {left.component.id}, {right.component.id}"
                )

    normalized = {
        "schema_version": COMPONENT_SCHEMA_VERSION,
        "components": [component.as_dict() for component in components],
    }
    return ComponentContract(
        schema_version=COMPONENT_SCHEMA_VERSION,
        components=tuple(components),
        digest_sha256=canonical_digest(normalized),
        spans=spans,
    )
