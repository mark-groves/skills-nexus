"""Contracts, orchestration, aggregation, and bounded capability-review exports."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skill_eval.core import (
    RUNTIME_EXCLUDED_NAMES,
    EvalError,
    EvalSpec,
    canonical_discovery_inputs,
    load_eval_spec,
    resolve_candidate_skill,
    resolve_skill,
    stable_digest,
)

PROFILE_SCHEMA_VERSION = 2
PROFILE_SCHEMA_VERSIONS = frozenset({1, 2})
CASE_GROUP_SCHEMA_VERSION = 1
ROUTINE_SCREEN_SCHEMA_VERSION = 1
DURABLE_SUMMARY_SCHEMA_VERSION = 2
CAPABILITY_REVIEW_SCHEMA_VERSION = 2
ORCHESTRATOR_VERSION = "capability-review-v2"
ROUTINE_ORCHESTRATOR_VERSION = "routine-screen-v1"
HARNESS_CONTRACT_VERSION = 1
JUDGE_PROTOCOL = "skill-eval-candidate-v3-condition-blind"
MAX_PROFILES = 16
MAX_CASE_GROUPS = 32
MAX_CASES_PER_KIND = 512
MAX_EXPORT_BYTES = 256_000
ROUTINE_BUDGET_SECONDS = 3_600
ROUTINE_DEADLINE_SECONDS = 3_300
ROUTINE_AGGREGATION_RESERVE_SECONDS = 300
EVAL_DIGEST_EXCLUDED_NAMES = frozenset({"reviews", "working", "__pycache__"})
SAFE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
PINNED_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
UNIX_ABSOLUTE_PATH_RE = re.compile(r"""(?:^|[\s=(\[{'\"`,;:])/(?!/)[^\s`]+""")
WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"""(?:(?:^|[\s=(\[{'\"`,;:])[A-Za-z]:[\\/]|"""
    r"""(?:^|[\s=(\[{'\"`,;])(?:\\\\|//)(?:[?.][\\/]|[^\\/\s`]+[\\/][^\\/\s`]+))"""
    r"""[^\s`]*"""
)
FILE_ABSOLUTE_PATH_RE = re.compile(
    r"""(?:^|[\s=(\[{'\"`,;:])file:/[^\s`]*""",
    re.IGNORECASE,
)
FORBIDDEN_EXPORT_KEYS = {
    "prompt",
    "prompts",
    "transcript",
    "transcripts",
    "command_output",
    "stdout",
    "stderr",
    "workspace",
    "workspace_path",
    "artifact",
    "artifacts",
    "event_trace",
    "events",
}
DISPOSITIONS = frozenset(
    {
        "retain",
        "compress",
        "move-to-reference",
        "replace-with-script",
        "remove-component",
        "merge-overlap",
        "retire",
        "insufficient-evidence",
    }
)

EvaluationRunner = Callable[[argparse.Namespace], tuple[dict[str, Any], Path]]

# Profile planning recognizes the adapters delivered by this integration stack
# without importing or constructing their runtime implementations. The Cursor
# runtime adapters are added by later issues; schema validation must still be
# able to describe their cells without requiring binaries or credentials.
PROFILE_TASK_ADAPTERS = frozenset({"codex", "cursor"})
PROFILE_JUDGE_ADAPTERS = frozenset({"codex", "cursor"})


@dataclass(frozen=True, order=True)
class AdapterFingerprint:
    """Exact task and judge adapter identity for one review cell."""

    task_adapter: str
    task_adapter_version: str
    judge_adapter: str
    judge_adapter_version: str

    def as_dict(self) -> dict[str, str]:
        return {
            "task_adapter": self.task_adapter,
            "task_adapter_version": self.task_adapter_version,
            "judge_adapter": self.judge_adapter,
            "judge_adapter_version": self.judge_adapter_version,
        }


def canonical_digest(value: object) -> str:
    """Hash JSON-compatible data without depending on a source path."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, *, label: str) -> object:
    """Load one JSON value with a user-actionable source label."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvalError(f"Missing {label}: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise EvalError(f"Unable to read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvalError(f"Invalid JSON in {label} {path}: {exc}") from exc


def _object(value: object, *, location: str) -> dict[str, Any]:
    """Require a JSON object at the named contract location."""
    if not isinstance(value, dict):
        raise EvalError(f"{location} must be an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, location: str) -> None:
    """Require an exact key set and report missing and unexpected keys."""
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
    """Validate a stable lowercase identifier used in paths and summaries."""
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise EvalError(
            f"{location} must be a lowercase kebab-case identifier between 1 and 64 characters"
        )
    return value


def _pinned_identifier(value: object, *, location: str) -> str:
    """Validate an immutable model or protocol identifier."""
    if not isinstance(value, str) or not value.strip():
        raise EvalError(f"{location} must be a non-empty explicit identifier")
    if value != value.strip():
        raise EvalError(f"{location} must not contain surrounding whitespace")
    result = value
    if result == "runtime-default":
        raise EvalError(
            f"{location} must pin an exact identifier; mutable runtime-default is not allowed"
        )
    if not PINNED_IDENTIFIER_RE.fullmatch(result):
        raise EvalError(
            f"{location} must use only letters, numbers, '.', '_', ':', '/', and '-' "
            "and be at most 160 characters"
        )
    return result


def _adapter_id(value: object, *, role: str, location: str) -> str:
    """Validate a profile adapter without constructing a runtime harness."""
    available = PROFILE_TASK_ADAPTERS if role == "task" else PROFILE_JUDGE_ADAPTERS
    if not isinstance(value, str) or value not in available:
        raise EvalError(
            f"Unknown {role} adapter {value!r} at {location}. Available {role} "
            f"adapters: {', '.join(sorted(available))}"
        )
    return value


def _pinned_model(value: object, *, adapter: str, location: str) -> str:
    """Reject mutable model selectors before any harness is constructed."""
    result = _pinned_identifier(value, location=location)
    if adapter == "cursor" and result.casefold() == "auto":
        raise EvalError(
            f"{location} must pin an exact identifier; mutable Cursor Auto is not allowed"
        )
    return result


@dataclass(frozen=True)
class JudgePolicy:
    id: str
    adapter: str
    model: str
    protocol: str

    def as_dict(self) -> dict[str, str]:
        """Return the normalized contract representation."""
        return {
            "id": self.id,
            "adapter": self.adapter,
            "model": self.model,
            "protocol": self.protocol,
        }


@dataclass(frozen=True)
class ModelProfile:
    id: str
    adapter: str
    model: str
    required: bool

    @property
    def role(self) -> str:
        """Return the profile's gating role."""
        return "required" if self.required else "observed"

    def as_dict(self) -> dict[str, Any]:
        """Return the normalized contract representation."""
        return {
            "id": self.id,
            "adapter": self.adapter,
            "model": self.model,
            "required": self.required,
        }


@dataclass(frozen=True)
class ProfileContract:
    schema_version: int
    source_schema_version: int
    judge_policy: JudgePolicy
    profiles: tuple[ModelProfile, ...]
    digest_sha256: str

    def as_dict(self) -> dict[str, Any]:
        """Return the normalized contract representation."""
        return {
            "schema_version": self.schema_version,
            "judge_policy": self.judge_policy.as_dict(),
            "profiles": [profile.as_dict() for profile in self.profiles],
        }


def load_profile_contract(path: Path) -> ProfileContract:
    """Load v2 or normalize a legacy v1 model-profile contract to canonical v2."""
    payload = _object(_load_json(path, label="model profile contract"), location=str(path))
    _exact_keys(payload, {"schema_version", "judge_policy", "profiles"}, location=str(path))
    source_schema_version = payload["schema_version"]
    if source_schema_version not in PROFILE_SCHEMA_VERSIONS:
        raise EvalError(
            f"{path}.schema_version must be one of {sorted(PROFILE_SCHEMA_VERSIONS)}, "
            f"found {source_schema_version!r}"
        )

    policy_payload = _object(payload["judge_policy"], location=f"{path}.judge_policy")
    _exact_keys(
        policy_payload,
        (
            {"id", "model", "protocol"}
            if source_schema_version == 1
            else {"id", "adapter", "model", "protocol"}
        ),
        location=f"{path}.judge_policy",
    )
    judge_adapter = (
        "codex"
        if source_schema_version == 1
        else _adapter_id(
            policy_payload["adapter"],
            role="judge",
            location=f"{path}.judge_policy.adapter",
        )
    )
    policy = JudgePolicy(
        id=_safe_id(policy_payload["id"], location=f"{path}.judge_policy.id"),
        adapter=judge_adapter,
        model=_pinned_model(
            policy_payload["model"],
            adapter=judge_adapter,
            location=f"{path}.judge_policy.model",
        ),
        protocol=_pinned_identifier(
            policy_payload["protocol"],
            location=f"{path}.judge_policy.protocol",
        ),
    )
    if policy.protocol != JUDGE_PROTOCOL:
        raise EvalError(f"{path}.judge_policy.protocol must be {JUDGE_PROTOCOL!r}")

    supplied_profiles = payload["profiles"]
    if not isinstance(supplied_profiles, list) or not supplied_profiles:
        raise EvalError(f"{path}.profiles must be a non-empty list")
    if len(supplied_profiles) > MAX_PROFILES:
        raise EvalError(f"{path}.profiles may contain at most {MAX_PROFILES} profiles")

    profiles: list[ModelProfile] = []
    seen: set[str] = set()
    for index, supplied in enumerate(supplied_profiles):
        location = f"{path}.profiles[{index}]"
        item = _object(supplied, location=location)
        _exact_keys(
            item,
            (
                {"id", "adapter", "model", "judge_model", "required"}
                if source_schema_version == 1
                else {"id", "adapter", "model", "required"}
            ),
            location=location,
        )
        profile_id = _safe_id(item["id"], location=f"{location}.id")
        if profile_id in seen:
            raise EvalError(f"Duplicate model profile id in {path}: {profile_id}")
        seen.add(profile_id)
        if source_schema_version == 1 and item["adapter"] != "codex":
            raise EvalError(
                f"{location}.adapter must be 'codex' in profile schema v1, "
                f"found {item['adapter']!r}"
            )
        task_adapter = _adapter_id(
            item["adapter"],
            role="task",
            location=f"{location}.adapter",
        )
        if not isinstance(item["required"], bool):
            raise EvalError(f"{location}.required must be boolean")
        if source_schema_version == 1:
            legacy_judge_model = _pinned_model(
                item["judge_model"],
                adapter="codex",
                location=f"{location}.judge_model",
            )
            if legacy_judge_model != policy.model:
                raise EvalError(
                    f"{location}.judge_model must match pinned judge_policy.model {policy.model!r}"
                )
        profile = ModelProfile(
            id=profile_id,
            adapter=task_adapter,
            model=_pinned_model(
                item["model"],
                adapter=task_adapter,
                location=f"{location}.model",
            ),
            required=item["required"],
        )
        profiles.append(profile)

    if not any(profile.required for profile in profiles):
        raise EvalError(f"{path}.profiles must contain at least one required profile")

    normalized = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "judge_policy": policy.as_dict(),
        "profiles": [profile.as_dict() for profile in profiles],
    }
    return ProfileContract(
        schema_version=PROFILE_SCHEMA_VERSION,
        source_schema_version=source_schema_version,
        judge_policy=policy,
        profiles=tuple(profiles),
        digest_sha256=canonical_digest(normalized),
    )


def select_profiles(
    contract: ProfileContract,
    observed_profile_ids: Iterable[str],
    *,
    include_all_observed: bool,
) -> tuple[ModelProfile, ...]:
    """Select every required profile and explicitly requested observed profiles."""
    requested = list(observed_profile_ids)
    duplicates = sorted(
        profile_id for profile_id in set(requested) if requested.count(profile_id) > 1
    )
    if duplicates:
        raise EvalError(f"Duplicate --observed-profile id(s): {', '.join(duplicates)}")
    by_id = {profile.id: profile for profile in contract.profiles}
    unknown = [profile_id for profile_id in requested if profile_id not in by_id]
    if unknown:
        raise EvalError(f"Unknown observed profile id(s): {', '.join(unknown)}")
    required_requested = [profile_id for profile_id in requested if by_id[profile_id].required]
    if required_requested:
        raise EvalError(
            "Required profiles always run and must not be selected with --observed-profile: "
            + ", ".join(required_requested)
        )
    requested_set = set(requested)
    return tuple(
        profile
        for profile in contract.profiles
        if profile.required
        or (not profile.required and (include_all_observed or profile.id in requested_set))
    )


@dataclass(frozen=True)
class CaseGroup:
    id: str
    kind: str
    trigger_cases: tuple[str, ...]
    behavior_cases: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return the normalized case-group representation."""
        return {
            "id": self.id,
            "kind": self.kind,
            "trigger_cases": list(self.trigger_cases),
            "behavior_cases": list(self.behavior_cases),
        }


@dataclass(frozen=True)
class RoutineScreenContract:
    """Repository-owned high-signal case selection for a routine screen."""

    schema_version: int
    trigger_cases: tuple[str, ...]
    behavior_cases: tuple[str, ...]
    digest_sha256: str

    def as_dict(self) -> dict[str, Any]:
        """Return the normalized routine-screen contract."""
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
    """Validate one bounded list of known trigger or behavior case IDs."""
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
    """Load a complete, non-overlapping development/held-back case partition."""
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
    """Load a bounded development-only routine selection.

    Routine screens intentionally avoid held-back cases. Changed discovery
    inputs use exactly one positive and one near-miss trigger case, while
    unchanged discovery inputs skip trigger execution and retain the selection
    only as the escalation contract.
    """
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


def validate_universes(
    requested: Iterable[str],
    limitation: str | None,
) -> tuple[str, ...]:
    """Default to both universes and require a documented limitation for one."""
    supplied = list(requested)
    universes = supplied or ["repository", "isolated"]
    duplicates = sorted(value for value in set(universes) if universes.count(value) > 1)
    if duplicates:
        raise EvalError(f"Duplicate --universe value(s): {', '.join(duplicates)}")
    unknown = sorted(set(universes) - {"repository", "isolated"})
    if unknown:
        raise EvalError(f"Unknown universe value(s): {', '.join(unknown)}")
    ordered = tuple(value for value in ("repository", "isolated") if value in universes)
    if len(ordered) == 1 and (limitation is None or not limitation.strip()):
        raise EvalError(
            "Selecting one skill universe requires --universe-limitation with a "
            "specific documented scope limitation"
        )
    if len(ordered) == 2 and limitation is not None:
        raise EvalError("--universe-limitation is only valid when selecting one universe")
    if limitation is not None and len(limitation.strip()) > 1000:
        raise EvalError("--universe-limitation must be at most 1000 characters")
    return ordered


@dataclass(frozen=True)
class CapabilityReviewConfig:
    repo_root: Path
    skill: str
    candidate: Path
    profile_source: Path
    contract: ProfileContract
    profiles: tuple[ModelProfile, ...]
    case_group_source: Path | None
    case_groups: tuple[CaseGroup, ...]
    universes: tuple[str, ...]
    universe_limitation: str | None
    trigger_repeats: int
    behavior_repeats: int
    activation_threshold: float
    jobs: int
    timeout: int
    codex_binary: str
    sandbox: str
    allow_fixture_scripts: bool
    output_root: Path
    expected_current_digest: str | None = None
    expected_candidate_digest: str | None = None
    expected_eval_digest: str | None = None
    expected_profiles_digest: str | None = None
    expected_case_groups_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate numeric controls when configuration enters the review system."""
        for value, name in (
            (self.trigger_repeats, "--trigger-repeats"),
            (self.behavior_repeats, "--behavior-repeats"),
            (self.jobs, "--jobs"),
            (self.timeout, "--timeout"),
        ):
            _positive_int(value, name=name)
        if not 0 <= self.activation_threshold <= 1:
            raise EvalError("--activation-threshold must be between 0 and 1")


@dataclass(frozen=True)
class RoutineScreenConfig:
    """Controls for the bounded, report-only routine screening workflow."""

    review: CapabilityReviewConfig
    contract_source: Path
    contract: RoutineScreenContract
    budget_seconds: int = ROUTINE_BUDGET_SECONDS
    deadline_seconds: int = ROUTINE_DEADLINE_SECONDS

    def __post_init__(self) -> None:
        """Enforce the fixed one-hour ceiling and five-minute aggregation reserve."""
        _positive_int(self.budget_seconds, name="--budget-seconds")
        _positive_int(self.deadline_seconds, name="--deadline-seconds")
        if self.budget_seconds > ROUTINE_BUDGET_SECONDS:
            raise EvalError(
                f"--budget-seconds may not exceed the routine ceiling of {ROUTINE_BUDGET_SECONDS}"
            )
        if self.budget_seconds <= ROUTINE_AGGREGATION_RESERVE_SECONDS:
            raise EvalError("--budget-seconds must exceed the five-minute aggregation reserve")
        maximum_deadline = min(
            ROUTINE_DEADLINE_SECONDS,
            self.budget_seconds - ROUTINE_AGGREGATION_RESERVE_SECONDS,
        )
        if self.deadline_seconds > maximum_deadline:
            raise EvalError(
                "--deadline-seconds must leave at least five minutes for bounded "
                f"aggregation and may not exceed {maximum_deadline}"
            )
        if self.review.trigger_repeats != 1 or self.review.behavior_repeats != 1:
            raise EvalError("Routine screens require exactly one trigger and behavior repeat")
        if self.review.jobs < 2:
            raise EvalError("Routine screens require --jobs of at least 2")
        if set(self.review.universes) != {"repository", "isolated"}:
            raise EvalError("Routine screens require both repository and isolated universes")
        if not self.review.profiles:
            raise EvalError("Routine screens require at least one required profile")
        if any(not profile.required for profile in self.review.profiles):
            raise EvalError("Routine screens run required profiles only")


def _positive_int(value: int, *, name: str) -> None:
    """Require a positive integer CLI control."""
    if isinstance(value, bool) or value <= 0:
        raise EvalError(f"{name} must be greater than zero")


def _verify_expected(name: str, expected: str | None, observed: str) -> None:
    """Verify an optional caller-pinned SHA-256 value."""
    if expected is None:
        return
    if not DIGEST_RE.fullmatch(expected):
        raise EvalError(f"{name} must be a lowercase 64-character SHA-256 digest")
    if expected != observed:
        raise EvalError(f"{name} mismatch: expected {expected}, observed {observed}")


def _review_policy_payload(spec: EvalSpec, contract: ProfileContract) -> dict[str, Any]:
    """Build the complete pinned judge-policy identity."""
    return {
        "judge_policy": contract.judge_policy.as_dict(),
        "evaluation_review_policy": (
            spec.review_policy.as_dict() if spec.review_policy is not None else None
        ),
        "grader_protocol": JUDGE_PROTOCOL,
    }


def _case_groups_digest(groups: tuple[CaseGroup, ...]) -> str:
    """Hash normalized case-group semantics independently of source paths."""
    return canonical_digest(
        {
            "schema_version": CASE_GROUP_SCHEMA_VERSION,
            "groups": [group.as_dict() for group in groups],
        }
    )


def _harness_manifest_digests(
    repo_root: Path,
    profiles: tuple[ModelProfile, ...],
    judge_policy: JudgePolicy,
) -> tuple[dict[str, str], str]:
    """Pin every selected task manifest and the global judge manifest."""
    task_digests: dict[str, str] = {}
    for adapter in sorted({profile.adapter for profile in profiles}):
        path = repo_root / "harnesses" / f"{adapter}.json"
        if not path.is_file():
            raise EvalError(f"Missing task harness manifest for adapter {adapter!r}: {path}")
        task_digests[adapter] = stable_digest(path)
    judge_path = repo_root / "harnesses" / f"{judge_policy.adapter}.json"
    if not judge_path.is_file():
        raise EvalError(
            f"Missing judge harness manifest for adapter {judge_policy.adapter!r}: {judge_path}"
        )
    return task_digests, stable_digest(judge_path)


def _safe_subset(value: object, keys: tuple[str, ...]) -> dict[str, Any]:
    """Copy only allowlisted keys from an optional mapping."""
    payload = value if isinstance(value, dict) else {}
    return {key: payload.get(key) for key in keys}


def _gate_summary(review: object) -> dict[str, Any]:
    """Reduce evaluator gates to durable, raw-evidence-free fields."""
    payload = review if isinstance(review, dict) else {}
    dimensions_payload = payload.get("dimensions")
    dimensions = dimensions_payload if isinstance(dimensions_payload, dict) else {}
    safe_dimensions: dict[str, Any] = {}
    for dimension_id in sorted(dimensions):
        dimension = dimensions[dimension_id]
        if not isinstance(dimension, dict):
            continue
        gates = []
        for gate in dimension.get("gates", []):
            if not isinstance(gate, dict):
                continue
            gates.append(
                {
                    "id": gate.get("id"),
                    "status": gate.get("status"),
                    "hard": gate.get("hard"),
                    "observed": gate.get("observed"),
                    "required": gate.get("required"),
                }
            )
        safe_dimensions[dimension_id] = {
            "status": dimension.get("status"),
            "gates": gates,
        }
    return {
        "verdict": payload.get("verdict"),
        "approved": payload.get("approved"),
        "hard_failure": payload.get("hard_failure"),
        "hard_blocked": payload.get("hard_blocked"),
        "trigger_gate_scope": _safe_subset(
            payload.get("trigger_gate_scope"),
            ("canonical_fields", "changed", "changed_fields", "trigger_gate_mode"),
        ),
        "dimensions": safe_dimensions,
        "no_aggregate_override": payload.get("no_aggregate_override"),
    }


def _condition_metrics(summary: dict[str, Any], condition: str) -> dict[str, Any]:
    """Extract bounded behavior and efficiency metrics for one condition."""
    grade = summary.get(condition)
    return {
        "behavior_checks": _safe_subset(
            grade,
            ("total", "passed", "failed", "unknown", "pass_rate", "evidence_coverage"),
        ),
        "case_pass_rate": (
            summary.get("case_pass_rate", {}).get(condition)
            if isinstance(summary.get("case_pass_rate"), dict)
            else None
        ),
        "efficiency": _safe_subset(
            summary.get("efficiency", {}).get(condition)
            if isinstance(summary.get("efficiency"), dict)
            else {},
            (
                "completed_runs",
                "failed_runs",
                "median_duration_seconds",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "median_tokens",
                "tool_calls",
            ),
        ),
    }


def _trigger_metrics(value: object) -> dict[str, Any]:
    """Extract bounded trigger metrics."""
    return _safe_subset(
        value,
        (
            "total",
            "completed",
            "correct",
            "accuracy",
            "recall",
            "specificity",
            "activation_rate",
            "run_errors",
        ),
    )


def _context_metrics(value: object) -> dict[str, Any]:
    """Extract portable context-footprint measurements."""
    payload = value if isinstance(value, dict) else {}
    return {
        "description": _safe_subset(
            payload.get("description"),
            ("characters", "utf8_bytes"),
        ),
        "skill_md_body": _safe_subset(
            payload.get("skill_md_body"),
            ("characters", "utf8_bytes"),
        ),
        "runtime_package": _safe_subset(
            payload.get("runtime_package"),
            ("file_count", "bytes", "digest_sha256"),
        ),
    }


def _cell_summary(
    result: dict[str, Any],
    *,
    profile: ModelProfile,
    judge_policy: JudgePolicy,
    universe: str,
    adapter_fingerprint: AdapterFingerprint,
    task_manifest_digest: str,
    judge_manifest_digest: str,
    groups: tuple[CaseGroup, ...],
    trigger_repeats: int,
    behavior_repeats: int,
) -> dict[str, Any]:
    """Build one durable profile/universe cell from a complete local result."""
    behavior_payload = result.get("behavior")
    behavior = behavior_payload if isinstance(behavior_payload, dict) else {}
    summary_payload = behavior.get("summary")
    summary = summary_payload if isinstance(summary_payload, dict) else {}
    trigger_payload = result.get("trigger")
    trigger = trigger_payload if isinstance(trigger_payload, dict) else {}
    candidate_trigger_payload = result.get("candidate_trigger")
    candidate_trigger = (
        candidate_trigger_payload if isinstance(candidate_trigger_payload, dict) else {}
    )
    runtime_payload = result.get("runtime")
    runtime = runtime_payload if isinstance(runtime_payload, dict) else {}
    context_payload = result.get("context_footprint")
    context = context_payload if isinstance(context_payload, dict) else {}
    comparison = result.get("candidate_comparison")
    safe_comparison = (
        _safe_subset(
            comparison,
            (
                "sign_convention",
                "candidate_minus_current_quality",
                "candidate_minus_current_quality_percentage_points",
                "candidate_lift_over_baseline",
                "candidate_lift_over_baseline_percentage_points",
                "static_reductions",
                "dynamic_input_token_reduction",
                "paired_checks",
            ),
        )
        if isinstance(comparison, dict)
        else {}
    )
    return {
        "profile_id": profile.id,
        "profile_role": profile.role,
        "universe": universe,
        "task_adapter": adapter_fingerprint.task_adapter,
        "task_model_requested": profile.model,
        "task_model_reported": runtime.get("task_model_reported"),
        "task_harness_version": adapter_fingerprint.task_adapter_version,
        "task_manifest_digest_sha256": task_manifest_digest,
        "judge_adapter": adapter_fingerprint.judge_adapter,
        "judge_model_requested": judge_policy.model,
        "judge_model_reported": runtime.get("judge_model_reported"),
        "judge_harness_version": adapter_fingerprint.judge_adapter_version,
        "judge_manifest_digest_sha256": judge_manifest_digest,
        # Compatibility aliases for schema-v1 durable-summary readers.
        "task_model": profile.model,
        "judge_model": judge_policy.model,
        "adapter_fingerprint": adapter_fingerprint.as_dict(),
        "runner_version": adapter_fingerprint.task_adapter_version,
        "verdict": (
            result.get("optimisation_review", {}).get("verdict")
            if isinstance(result.get("optimisation_review"), dict)
            else "insufficient-evidence"
        ),
        "metrics": {
            "baseline": _condition_metrics(summary, "baseline"),
            "current": _condition_metrics(summary, "skill"),
            "candidate": _condition_metrics(summary, "candidate"),
            "triggering": {
                "current": _trigger_metrics(trigger.get("summary")),
                "candidate": _trigger_metrics(candidate_trigger.get("summary")),
            },
            "candidate_comparison": safe_comparison,
        },
        "context_footprint": {
            "baseline": _context_metrics(context.get("baseline")),
            "current": _context_metrics(context.get("skill")),
            "candidate": _context_metrics(context.get("candidate")),
        },
        "gates": _gate_summary(result.get("optimisation_review")),
        "case_group_coverage": [
            {
                **group.as_dict(),
                "trigger_repeats": trigger_repeats,
                "behavior_repeats": behavior_repeats,
            }
            for group in groups
        ],
    }


def _validate_result(
    result: dict[str, Any],
    *,
    profile: ModelProfile,
    judge_policy: JudgePolicy,
    universe: str,
    current_digest: str,
    candidate_digest: str,
    eval_spec_digest: str,
    expected_trigger_cases: tuple[str, ...] | None = None,
    expected_behavior_cases: tuple[str, ...] | None = None,
    expected_trigger_repeats: int | None = None,
    expected_behavior_repeats: int | None = None,
    expected_deadline_seconds: int | None = None,
) -> AdapterFingerprint:
    """Verify a cell used the pinned models, digests, universe, and schema."""
    if result.get("schema_version") != 3:
        raise EvalError(
            f"Profile {profile.id} in {universe} did not produce candidate schema version 3"
        )
    skill = result.get("skill")
    candidate = result.get("candidate")
    runtime = result.get("runtime")
    if (
        not isinstance(skill, dict)
        or not isinstance(candidate, dict)
        or not isinstance(runtime, dict)
    ):
        raise EvalError(f"Profile {profile.id} in {universe} returned an incomplete result")
    checks = (
        ("current digest", skill.get("runtime_digest_sha256"), current_digest),
        ("candidate digest", candidate.get("runtime_digest_sha256"), candidate_digest),
        (
            "evaluation spec digest",
            skill.get("eval_spec_digest_sha256"),
            eval_spec_digest,
        ),
        ("task adapter", runtime.get("task_adapter"), profile.adapter),
        ("judge adapter", runtime.get("judge_adapter"), judge_policy.adapter),
        ("requested task model", runtime.get("task_model_requested"), profile.model),
        ("reported task model", runtime.get("task_model_reported"), profile.model),
        ("requested judge model", runtime.get("judge_model_requested"), judge_policy.model),
        ("reported judge model", runtime.get("judge_model_reported"), judge_policy.model),
        ("task model compatibility alias", runtime.get("model"), profile.model),
        ("judge model compatibility alias", runtime.get("judge_model"), judge_policy.model),
        ("skill universe", runtime.get("skill_universe"), universe),
    )
    for label, observed, expected in checks:
        if observed != expected:
            raise EvalError(
                f"Profile {profile.id} in {universe} changed pinned {label}: "
                f"expected {expected!r}, observed {observed!r}"
            )
    if not isinstance(result.get("optimisation_review"), dict):
        raise EvalError(f"Profile {profile.id} in {universe} did not produce optimisation gates")
    if any(
        value is not None
        for value in (
            expected_trigger_cases,
            expected_behavior_cases,
            expected_trigger_repeats,
            expected_behavior_repeats,
            expected_deadline_seconds,
        )
    ):
        run_config = result.get("config")
        if not isinstance(run_config, dict):
            raise EvalError(f"Profile {profile.id} in {universe} omitted evaluator controls")
        control_checks = (
            ("trigger cases", run_config.get("trigger_case_ids"), expected_trigger_cases),
            ("behavior cases", run_config.get("behavior_case_ids"), expected_behavior_cases),
            ("trigger repeats", run_config.get("trigger_repeats"), expected_trigger_repeats),
            ("behavior repeats", run_config.get("behavior_repeats"), expected_behavior_repeats),
            ("deadline", runtime.get("deadline_seconds"), expected_deadline_seconds),
        )
        for control_label, observed_control, expected_control in control_checks:
            normalized_expected = (
                list(expected_control) if isinstance(expected_control, tuple) else expected_control
            )
            if expected_control is not None and observed_control != normalized_expected:
                raise EvalError(
                    f"Profile {profile.id} in {universe} changed pinned {control_label}: "
                    f"expected {normalized_expected!r}, observed {observed_control!r}"
                )
    task_adapter = runtime.get("task_adapter")
    task_version = runtime.get("task_adapter_version")
    if not isinstance(task_version, str) or not task_version.strip():
        legacy_version = runtime.get("codex_version")
        task_version = (
            legacy_version
            if task_adapter == "codex"
            and isinstance(legacy_version, str)
            and legacy_version.strip()
            else None
        )
    if not isinstance(task_version, str) or not task_version.strip():
        raise EvalError(
            f"Profile {profile.id} in {universe} did not report an exact task adapter version"
        )
    judge_version = runtime.get("judge_adapter_version")
    if not isinstance(judge_version, str) or not judge_version.strip():
        raise EvalError(
            f"Profile {profile.id} in {universe} did not report an exact judge adapter version"
        )
    return AdapterFingerprint(
        task_adapter=profile.adapter,
        task_adapter_version=task_version,
        judge_adapter=judge_policy.adapter,
        judge_adapter_version=judge_version,
    )


def _build_eval_args(
    config: CapabilityReviewConfig,
    *,
    profile: ModelProfile,
    universe: str,
    cell_root: Path,
    trigger_cases: tuple[str, ...] | None = None,
    behavior_cases: tuple[str, ...] | None = None,
    deadline_seconds: int | None = None,
) -> argparse.Namespace:
    """Construct one evaluator invocation from review controls."""
    from eval_skills import build_parser

    selected_trigger = trigger_cases
    selected_behavior = behavior_cases
    argv = [
        "--skill",
        config.skill,
        "--candidate",
        str(config.candidate),
        "--suite",
        "all" if selected_trigger is None or selected_trigger else "behavior",
        "--trigger-repeats",
        str(config.trigger_repeats),
        "--behavior-repeats",
        str(config.behavior_repeats),
        "--activation-threshold",
        str(config.activation_threshold),
        "--jobs",
        str(config.jobs),
        "--timeout",
        str(config.timeout),
        "--task-adapter",
        profile.adapter,
        "--judge-adapter",
        config.contract.judge_policy.adapter,
        "--model",
        profile.model,
        "--judge-model",
        config.contract.judge_policy.model,
        "--codex-binary",
        config.codex_binary,
        "--skill-universe",
        universe,
        "--sandbox",
        config.sandbox,
        (
            "--allow-fixture-scripts"
            if config.allow_fixture_scripts
            else "--no-allow-fixture-scripts"
        ),
        "--output-root",
        str(cell_root),
        "--repo-root",
        str(config.repo_root),
    ]
    if selected_trigger is not None:
        for case_id in selected_trigger:
            argv.extend(["--trigger-case", case_id])
    if selected_behavior is not None:
        for case_id in selected_behavior:
            argv.extend(["--behavior-case", case_id])
    if deadline_seconds is not None:
        argv.extend(["--deadline-seconds", str(deadline_seconds)])
    return build_parser().parse_args(argv)


def _aggregate_profiles(
    profiles: tuple[ModelProfile, ...],
    cells: list[dict[str, Any]],
    *,
    groups: tuple[CaseGroup, ...],
) -> dict[str, Any]:
    """Aggregate cell gates while keeping observed profiles non-blocking."""
    severity = {"rejected": 3, "insufficient-evidence": 2, "approved": 1}
    profile_results: list[dict[str, Any]] = []
    for profile in profiles:
        cell_verdicts = [
            {
                "universe": cell["universe"],
                "verdict": cell["verdict"],
            }
            for cell in cells
            if cell["profile_id"] == profile.id
        ]
        worst = max(
            (item["verdict"] for item in cell_verdicts),
            key=lambda verdict: severity.get(verdict, 2),
        )
        status = (
            "pass"
            if worst == "approved"
            else "fail"
            if worst == "rejected"
            else "insufficient-evidence"
        )
        profile_results.append(
            {
                "id": profile.id,
                "role": profile.role,
                "status": status,
                "cells": cell_verdicts,
            }
        )

    held_back = [group.id for group in groups if group.kind == "held-back"]
    development = [group.id for group in groups if group.kind == "development"]
    repeated = all(
        cell["case_group_coverage"]
        and all(
            group["trigger_repeats"] >= 2 and group["behavior_repeats"] >= 2
            for group in cell["case_group_coverage"]
        )
        for cell in cells
    )
    coverage_status = "pass" if held_back and development and repeated else "insufficient-evidence"
    required = [item for item in profile_results if item["role"] == "required"]
    if any(item["status"] == "fail" for item in required):
        verdict = "rejected"
    elif coverage_status != "pass" or any(item["status"] != "pass" for item in required):
        verdict = "insufficient-evidence"
    else:
        verdict = "approved"
    return {
        "verdict": verdict,
        "required_profiles_block": True,
        "observed_profiles_block": False,
        "profile_results": profile_results,
        "required_blockers": [item["id"] for item in required if item["status"] != "pass"],
        "observed_failures": [
            item["id"]
            for item in profile_results
            if item["role"] == "observed" and item["status"] != "pass"
        ],
        "coverage_gate": {
            "status": coverage_status,
            "development_groups": development,
            "held_back_groups": held_back,
            "repeated": repeated,
            "detail": (
                "Case groups are declarative partition labels and process controls, "
                "not measured per-group efficacy; metrics and gates remain whole-suite. "
                "A pass requires at least one development group and held-back group "
                "with two or more trigger and behavior repeats."
            ),
        },
        "no_aggregate_override": True,
    }


def _assert_pinned_sources(
    config: CapabilityReviewConfig,
    *,
    skill_dir: Path,
    candidate_dir: Path,
    spec: EvalSpec,
    current_digest: str,
    candidate_digest: str,
    eval_digest: str,
    task_manifest_digests: dict[str, str],
    judge_manifest_digest: str,
    groups_digest: str,
) -> None:
    """Reject material input drift between matrix cells."""
    observed = {
        "Current runtime package": stable_digest(
            skill_dir,
            exclude=RUNTIME_EXCLUDED_NAMES,
        ),
        "Candidate runtime package": stable_digest(
            candidate_dir,
            exclude=RUNTIME_EXCLUDED_NAMES,
        ),
        "evaluation bundle": stable_digest(
            spec.path.parent,
            exclude=EVAL_DIGEST_EXCLUDED_NAMES,
        ),
        "model profile contract": load_profile_contract(config.profile_source).digest_sha256,
        "case group definition": _case_groups_digest(
            load_case_groups(config.case_group_source, spec)
        ),
    }
    expected = {
        "Current runtime package": current_digest,
        "Candidate runtime package": candidate_digest,
        "evaluation bundle": eval_digest,
        "model profile contract": config.contract.digest_sha256,
        "case group definition": groups_digest,
    }
    for label, observed_digest in observed.items():
        if observed_digest != expected[label]:
            raise EvalError(
                f"{label} changed during the capability review: "
                f"expected {expected[label]}, observed {observed_digest}"
            )
    observed_task_digests, observed_judge_digest = _harness_manifest_digests(
        config.repo_root.resolve(),
        config.profiles,
        config.contract.judge_policy,
    )
    if observed_task_digests != task_manifest_digests:
        raise EvalError(
            "Task harness manifests changed during the capability review: "
            f"expected {task_manifest_digests}, observed {observed_task_digests}"
        )
    if observed_judge_digest != judge_manifest_digest:
        raise EvalError(
            "Judge harness manifest changed during the capability review: "
            f"expected {judge_manifest_digest}, observed {observed_judge_digest}"
        )


def run_capability_review(
    config: CapabilityReviewConfig,
    evaluation_runner: EvaluationRunner,
) -> tuple[dict[str, Any], Path]:
    """Run every selected profile in the selected universes and retain full local runs."""
    if not config.profiles:
        raise EvalError("At least one selected model profile is required")
    if not any(profile.required for profile in config.profiles):
        raise EvalError("Every capability review must include a required profile")
    if not config.universes or set(config.universes) - {"repository", "isolated"}:
        raise EvalError("Capability review universes must be repository, isolated, or both")

    repo_root = config.repo_root.resolve()
    skill_dir = resolve_skill(repo_root, config.skill)
    candidate_dir = resolve_candidate_skill(repo_root, config.candidate, skill_dir.name)
    spec = load_eval_spec(skill_dir, repo_root / "evals")
    current_digest = stable_digest(skill_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    candidate_digest = stable_digest(candidate_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    eval_spec_digest = stable_digest(spec.path)
    eval_digest = stable_digest(
        spec.path.parent,
        exclude=EVAL_DIGEST_EXCLUDED_NAMES,
    )
    groups_digest = _case_groups_digest(config.case_groups)
    judge_policy = _review_policy_payload(spec, config.contract)
    judge_policy_digest = canonical_digest(judge_policy)
    task_manifest_digests, judge_manifest_digest = _harness_manifest_digests(
        repo_root,
        config.profiles,
        config.contract.judge_policy,
    )

    _verify_expected(
        "--expected-current-digest",
        config.expected_current_digest,
        current_digest,
    )
    _verify_expected(
        "--expected-candidate-digest",
        config.expected_candidate_digest,
        candidate_digest,
    )
    _verify_expected("--expected-eval-digest", config.expected_eval_digest, eval_digest)
    _verify_expected(
        "--expected-profiles-digest",
        config.expected_profiles_digest,
        config.contract.digest_sha256,
    )
    _verify_expected(
        "--expected-case-groups-digest",
        config.expected_case_groups_digest,
        groups_digest,
    )

    pinned_inputs = {
        "skill": spec.skill_name,
        "current_digest_sha256": current_digest,
        "candidate_digest_sha256": candidate_digest,
        "eval_digest_sha256": eval_digest,
        "eval_spec_digest_sha256": eval_spec_digest,
        "profiles_digest_sha256": config.contract.digest_sha256,
        "case_groups_digest_sha256": groups_digest,
        "judge_policy_digest_sha256": judge_policy_digest,
        "task_harness_manifest_digests_sha256": task_manifest_digests,
        "judge_harness_manifest_digest_sha256": judge_manifest_digest,
        "harness_manifest_digest_sha256": (
            task_manifest_digests.get("codex")
            if set(task_manifest_digests) == {"codex"}
            and config.contract.judge_policy.adapter == "codex"
            else None
        ),
        "profiles": [profile.id for profile in config.profiles],
        "universes": list(config.universes),
        "trigger_repeats": config.trigger_repeats,
        "behavior_repeats": config.behavior_repeats,
    }
    input_digest = canonical_digest(pinned_inputs)
    timestamp = datetime.now(UTC)
    local_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{input_digest[:12]}"
    local_root = config.output_root.resolve() / spec.skill_name / "capability-reviews" / local_id
    suffix = 1
    while local_root.exists():
        local_root = local_root.with_name(f"{local_id}-{suffix}")
        suffix += 1
    local_root.mkdir(parents=True)

    local_manifest: dict[str, Any] = {
        "schema_version": CAPABILITY_REVIEW_SCHEMA_VERSION,
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "status": "running",
        "started_at": timestamp.isoformat(),
        "pinned_inputs": pinned_inputs,
        "sources": {
            "repository": str(repo_root),
            "skill": str(skill_dir),
            "candidate": str(candidate_dir),
            "profiles": str(config.profile_source.resolve()),
            "case_groups": (
                str(config.case_group_source.resolve())
                if config.case_group_source is not None
                else None
            ),
        },
        "cells": [],
    }
    _write_json(local_root / "review.json", local_manifest)

    cells: list[dict[str, Any]] = []
    task_versions: dict[str, str] = {}
    judge_version: str | None = None
    try:
        for profile in config.profiles:
            for universe in config.universes:
                _assert_pinned_sources(
                    config,
                    skill_dir=skill_dir,
                    candidate_dir=candidate_dir,
                    spec=spec,
                    current_digest=current_digest,
                    candidate_digest=candidate_digest,
                    eval_digest=eval_digest,
                    task_manifest_digests=task_manifest_digests,
                    judge_manifest_digest=judge_manifest_digest,
                    groups_digest=groups_digest,
                )
                cell_root = local_root / "profiles" / profile.id / universe
                args = _build_eval_args(
                    config,
                    profile=profile,
                    universe=universe,
                    cell_root=cell_root,
                )
                result, run_dir = evaluation_runner(args)
                try:
                    run_dir.resolve().relative_to(cell_root.resolve())
                except ValueError as exc:
                    raise EvalError(
                        f"Profile {profile.id} in {universe} wrote outside its local "
                        f"review root: {run_dir}"
                    ) from exc
                if not (run_dir / "results.json").is_file():
                    raise EvalError(
                        f"Profile {profile.id} in {universe} did not retain results.json "
                        "under the local review root"
                    )
                observed_fingerprint = _validate_result(
                    result,
                    profile=profile,
                    judge_policy=config.contract.judge_policy,
                    universe=universe,
                    current_digest=current_digest,
                    candidate_digest=candidate_digest,
                    eval_spec_digest=eval_spec_digest,
                )
                observed_task_version = observed_fingerprint.task_adapter_version
                prior_task_version = task_versions.setdefault(
                    profile.adapter,
                    observed_task_version,
                )
                if prior_task_version != observed_task_version:
                    raise EvalError(
                        f"Task harness version for {profile.adapter!r} changed during the "
                        f"capability review: {prior_task_version!r} then "
                        f"{observed_task_version!r}"
                    )
                observed_judge_version = observed_fingerprint.judge_adapter_version
                if judge_version is None:
                    judge_version = observed_judge_version
                elif judge_version != observed_judge_version:
                    raise EvalError(
                        "Judge harness version changed during the capability review: "
                        f"{judge_version!r} then {observed_judge_version!r}"
                    )
                cell = _cell_summary(
                    result,
                    profile=profile,
                    judge_policy=config.contract.judge_policy,
                    universe=universe,
                    adapter_fingerprint=observed_fingerprint,
                    task_manifest_digest=task_manifest_digests[profile.adapter],
                    judge_manifest_digest=judge_manifest_digest,
                    groups=config.case_groups,
                    trigger_repeats=config.trigger_repeats,
                    behavior_repeats=config.behavior_repeats,
                )
                cells.append(cell)
                local_manifest["cells"].append(
                    {
                        "profile_id": profile.id,
                        "profile_role": profile.role,
                        "universe": universe,
                        "verdict": cell["verdict"],
                        "run_directory": str(run_dir.resolve()),
                        "results_file": str((run_dir / "results.json").resolve()),
                    }
                )
                _write_json(local_root / "review.json", local_manifest)
        _assert_pinned_sources(
            config,
            skill_dir=skill_dir,
            candidate_dir=candidate_dir,
            spec=spec,
            current_digest=current_digest,
            candidate_digest=candidate_digest,
            eval_digest=eval_digest,
            task_manifest_digests=task_manifest_digests,
            judge_manifest_digest=judge_manifest_digest,
            groups_digest=groups_digest,
        )
    except Exception as exc:
        local_manifest["status"] = "failed"
        local_manifest["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(local_root / "review.json", local_manifest)
        raise

    aggregate = _aggregate_profiles(config.profiles, cells, groups=config.case_groups)
    local_manifest["status"] = "completed"
    local_manifest["completed_at"] = datetime.now(UTC).isoformat()
    local_manifest["task_harness_versions"] = task_versions
    local_manifest["judge_harness_version"] = judge_version
    local_manifest["aggregate"] = aggregate
    _write_json(local_root / "review.json", local_manifest)

    review = {
        "schema_version": CAPABILITY_REVIEW_SCHEMA_VERSION,
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "local_review_id": local_root.name,
        "pinned_inputs": {
            **pinned_inputs,
            "judge_policy": judge_policy,
        },
        "task_harnesses": [
            {
                "adapter": adapter,
                "version": task_versions.get(adapter),
                "contract_version": HARNESS_CONTRACT_VERSION,
                "manifest_digest_sha256": digest,
            }
            for adapter, digest in sorted(task_manifest_digests.items())
        ],
        "judge_harness": {
            "adapter": config.contract.judge_policy.adapter,
            "version": judge_version,
            "contract_version": HARNESS_CONTRACT_VERSION,
            "manifest_digest_sha256": judge_manifest_digest,
        },
        "profiles": [
            {
                "id": profile.id,
                "role": profile.role,
                "adapter": profile.adapter,
                "task_model": profile.model,
                "judge_adapter": config.contract.judge_policy.adapter,
                "judge_model": config.contract.judge_policy.model,
            }
            for profile in config.profiles
        ],
        "unselected_observed_profiles": [
            profile.id
            for profile in config.contract.profiles
            if not profile.required and profile not in config.profiles
        ],
        "coverage": {
            "universes": list(config.universes),
            "both_universes": set(config.universes) == {"repository", "isolated"},
            "single_universe_limitation": (
                config.universe_limitation.strip()
                if len(config.universes) == 1 and config.universe_limitation is not None
                else None
            ),
            "case_groups": [group.as_dict() for group in config.case_groups],
            "trigger_repeats": config.trigger_repeats,
            "behavior_repeats": config.behavior_repeats,
        },
        "cells": cells,
        "aggregate": aggregate,
    }
    return review, local_root


def _routine_gate_map(cell: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """Index one bounded cell's gates by stable identifier."""
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    dimensions = cell.get("gates", {}).get("dimensions", {})
    if not isinstance(dimensions, dict):
        return result
    for dimension_id, dimension in dimensions.items():
        if not isinstance(dimension, dict):
            continue
        for gate in dimension.get("gates", []):
            if isinstance(gate, dict) and isinstance(gate.get("id"), str):
                result[gate["id"]] = (str(dimension_id), gate)
    return result


def _routine_cell_status(
    cell: dict[str, Any],
    *,
    discovery_changed: bool,
    protected_gate_ids: tuple[str, ...],
) -> tuple[str, list[str]]:
    """Reduce one filtered cell without turning it into approval evidence."""
    gate_map = _routine_gate_map(cell)
    required_gate_ids = {
        "candidate-non-inferiority",
        "retained-skill-baseline-value",
        "meaningful-context-reduction",
        "repository-review-policy",
        "behavior-evidence-coverage",
        "execution-completeness",
        "judgment-completeness",
        "fixture-fidelity",
        "fixture-parity",
        "condition-blind-grading",
    }
    if discovery_changed:
        required_gate_ids.update({"recall-non-inferiority", "specificity-non-inferiority"})
    required_gate_ids.update(protected_gate_ids)
    missing = sorted(required_gate_ids - set(gate_map))
    if missing:
        return "incomplete", ["missing gate(s): " + ", ".join(missing)]

    blockers: list[str] = []
    substantive_failures: list[str] = []
    intentionally_non_approving = {
        "complete-suite-coverage",
        "minimum-trigger-repeats",
        "minimum-behavior-repeats",
    }
    for gate_id, (dimension_id, gate) in gate_map.items():
        status = gate.get("status")
        hard = gate.get("hard") is True
        if gate_id in intentionally_non_approving:
            continue
        if gate_id == "execution-completeness" and not discovery_changed:
            observed = gate.get("observed")
            behavior_errors = (
                observed.get("behavior_failed_runs") if isinstance(observed, dict) else None
            )
            if (
                isinstance(behavior_errors, dict)
                and set(behavior_errors) == {"skill", "baseline", "candidate"}
                and all(value == 0 for value in behavior_errors.values())
            ):
                continue
        if status == "pass" or (
            not hard and not discovery_changed and dimension_id == "triggering"
        ):
            continue
        if status == "fail" and dimension_id in {
            "correctness",
            "safety",
            "triggering",
            "context",
        }:
            substantive_failures.append(gate_id)
        else:
            blockers.append(f"{gate_id}: {status}")

    if substantive_failures:
        return "reject", substantive_failures + blockers
    if blockers:
        return "incomplete", blockers
    return "eligible-for-escalation", []


def _aggregate_routine_screen(
    profiles: tuple[ModelProfile, ...],
    cells: list[dict[str, Any]],
    *,
    discovery_changed: bool,
    protected_gate_ids: tuple[str, ...],
    cell_errors: list[dict[str, str]],
) -> dict[str, Any]:
    """Aggregate required routine cells into a report-only outcome."""
    expected = {
        (profile.id, universe) for profile in profiles for universe in ("repository", "isolated")
    }
    observed = {(cell["profile_id"], cell["universe"]) for cell in cells}
    missing = sorted(expected - observed)
    cell_results = []
    for cell in sorted(cells, key=lambda item: (item["profile_id"], item["universe"])):
        status, blockers = _routine_cell_status(
            cell,
            discovery_changed=discovery_changed,
            protected_gate_ids=protected_gate_ids,
        )
        cell_results.append(
            {
                "profile_id": cell["profile_id"],
                "universe": cell["universe"],
                "status": status,
                "blockers": blockers,
            }
        )
    if any(item["status"] == "reject" for item in cell_results):
        outcome = "reject"
    elif cell_errors or missing or any(item["status"] == "incomplete" for item in cell_results):
        outcome = "incomplete"
    elif cell_results:
        outcome = "eligible-for-escalation"
    else:
        outcome = "incomplete"
    return {
        "outcome": outcome,
        "report_only": True,
        "approval_possible": False,
        "automatic_promotion": False,
        "cell_results": cell_results,
        "cell_errors": cell_errors,
        "missing_cells": [
            {"profile_id": profile_id, "universe": universe} for profile_id, universe in missing
        ],
        "detail": (
            "Eligibility permits only a human-opted full escalation. It is not "
            "approval or promotion evidence."
        ),
    }


def run_routine_screen(
    config: RoutineScreenConfig,
    evaluation_runner: EvaluationRunner,
) -> tuple[dict[str, Any], Path]:
    """Run the bounded routine screen concurrently across both universes."""
    review_config = config.review
    repo_root = review_config.repo_root.resolve()
    skill_dir = resolve_skill(repo_root, review_config.skill)
    candidate_dir = resolve_candidate_skill(
        repo_root,
        review_config.candidate,
        skill_dir.name,
    )
    spec = load_eval_spec(skill_dir, repo_root / "evals")
    current_digest = stable_digest(skill_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    candidate_digest = stable_digest(candidate_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    eval_spec_digest = stable_digest(spec.path)
    eval_digest = stable_digest(
        spec.path.parent,
        exclude=EVAL_DIGEST_EXCLUDED_NAMES,
    )
    groups_digest = _case_groups_digest(review_config.case_groups)
    judge_policy_digest = canonical_digest(_review_policy_payload(spec, review_config.contract))
    task_manifest_digests, judge_manifest_digest = _harness_manifest_digests(
        repo_root,
        review_config.profiles,
        review_config.contract.judge_policy,
    )
    current_discovery = canonical_discovery_inputs(skill_dir)
    candidate_discovery = canonical_discovery_inputs(candidate_dir)
    changed_fields = [
        field
        for field in ("name", "description")
        if current_discovery[field] != candidate_discovery[field]
    ]
    discovery_changed = bool(changed_fields)
    selected_trigger = config.contract.trigger_cases if discovery_changed else ()
    behavior_by_id = {case.id: case for case in spec.behavior_cases}
    protected_gate_ids = tuple(
        f"protected-check:{check.id}"
        for case_id in config.contract.behavior_cases
        for check in behavior_by_id[case_id].checks
        if check.gate == "hard"
    )
    routine_groups = (
        CaseGroup(
            id="routine-development",
            kind="development",
            trigger_cases=selected_trigger,
            behavior_cases=config.contract.behavior_cases,
        ),
    )

    _verify_expected(
        "--expected-current-digest",
        review_config.expected_current_digest,
        current_digest,
    )
    _verify_expected(
        "--expected-candidate-digest",
        review_config.expected_candidate_digest,
        candidate_digest,
    )
    _verify_expected("--expected-eval-digest", review_config.expected_eval_digest, eval_digest)
    _verify_expected(
        "--expected-profiles-digest",
        review_config.expected_profiles_digest,
        review_config.contract.digest_sha256,
    )
    _verify_expected(
        "--expected-case-groups-digest",
        review_config.expected_case_groups_digest,
        groups_digest,
    )

    pinned_inputs = {
        "skill": spec.skill_name,
        "current_digest_sha256": current_digest,
        "candidate_digest_sha256": candidate_digest,
        "eval_digest_sha256": eval_digest,
        "eval_spec_digest_sha256": eval_spec_digest,
        "profiles_digest_sha256": review_config.contract.digest_sha256,
        "case_groups_digest_sha256": groups_digest,
        "routine_contract_digest_sha256": config.contract.digest_sha256,
        "judge_policy_digest_sha256": judge_policy_digest,
        "task_harness_manifest_digests_sha256": task_manifest_digests,
        "judge_harness_manifest_digest_sha256": judge_manifest_digest,
        "harness_manifest_digest_sha256": (
            task_manifest_digests.get("codex")
            if set(task_manifest_digests) == {"codex"}
            and review_config.contract.judge_policy.adapter == "codex"
            else None
        ),
        "profiles": [profile.id for profile in review_config.profiles],
        "universes": ["repository", "isolated"],
        "trigger_repeats": 1,
        "behavior_repeats": 1,
        "trigger_cases": list(selected_trigger),
        "behavior_cases": list(config.contract.behavior_cases),
        "protected_gate_ids": list(protected_gate_ids),
        "discovery_inputs_changed": discovery_changed,
        "changed_discovery_fields": changed_fields,
        "budget_seconds": config.budget_seconds,
        "deadline_seconds": config.deadline_seconds,
    }
    input_digest = canonical_digest(pinned_inputs)
    timestamp = datetime.now(UTC)
    local_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{input_digest[:12]}"
    local_root = (
        review_config.output_root.resolve() / spec.skill_name / "routine-screens" / local_id
    )
    suffix = 1
    while local_root.exists():
        local_root = local_root.with_name(f"{local_id}-{suffix}")
        suffix += 1
    local_root.mkdir(parents=True)
    local_manifest: dict[str, Any] = {
        "schema_version": 1,
        "workflow": "routine",
        "orchestrator_version": ROUTINE_ORCHESTRATOR_VERSION,
        "status": "running",
        "started_at": timestamp.isoformat(),
        "pinned_inputs": pinned_inputs,
        "cells": [],
    }
    _write_json(local_root / "review.json", local_manifest)

    def run_cell(
        profile: ModelProfile, universe: str
    ) -> tuple[dict[str, Any], dict[str, Any], AdapterFingerprint]:
        _assert_pinned_sources(
            review_config,
            skill_dir=skill_dir,
            candidate_dir=candidate_dir,
            spec=spec,
            current_digest=current_digest,
            candidate_digest=candidate_digest,
            eval_digest=eval_digest,
            task_manifest_digests=task_manifest_digests,
            judge_manifest_digest=judge_manifest_digest,
            groups_digest=groups_digest,
        )
        observed_contract = load_routine_screen_contract(
            config.contract_source,
            spec,
            review_config.case_groups,
        )
        if observed_contract.digest_sha256 != config.contract.digest_sha256:
            raise EvalError("Routine screen contract changed during the evaluation")
        cell_root = local_root / "profiles" / profile.id / universe
        args = _build_eval_args(
            review_config,
            profile=profile,
            universe=universe,
            cell_root=cell_root,
            trigger_cases=selected_trigger,
            behavior_cases=config.contract.behavior_cases,
            deadline_seconds=config.deadline_seconds,
        )
        result, run_dir = evaluation_runner(args)
        try:
            run_dir.resolve().relative_to(cell_root.resolve())
        except ValueError as exc:
            raise EvalError(
                f"Profile {profile.id} in {universe} wrote outside its local "
                f"routine root: {run_dir}"
            ) from exc
        if not (run_dir / "results.json").is_file():
            raise EvalError(
                f"Profile {profile.id} in {universe} did not retain results.json "
                "under the local routine root"
            )
        adapter_fingerprint = _validate_result(
            result,
            profile=profile,
            judge_policy=review_config.contract.judge_policy,
            universe=universe,
            current_digest=current_digest,
            candidate_digest=candidate_digest,
            eval_spec_digest=eval_spec_digest,
            expected_trigger_cases=selected_trigger,
            expected_behavior_cases=config.contract.behavior_cases,
            expected_trigger_repeats=1,
            expected_behavior_repeats=1,
            expected_deadline_seconds=config.deadline_seconds,
        )
        cell = _cell_summary(
            result,
            profile=profile,
            judge_policy=review_config.contract.judge_policy,
            universe=universe,
            adapter_fingerprint=adapter_fingerprint,
            task_manifest_digest=task_manifest_digests[profile.adapter],
            judge_manifest_digest=judge_manifest_digest,
            groups=routine_groups,
            trigger_repeats=1,
            behavior_repeats=1,
        )
        manifest_cell = {
            "profile_id": profile.id,
            "profile_role": profile.role,
            "universe": universe,
            "verdict": cell["verdict"],
            "run_directory": str(run_dir.resolve()),
            "results_file": str((run_dir / "results.json").resolve()),
        }
        return cell, manifest_cell, adapter_fingerprint

    cells: list[dict[str, Any]] = []
    cell_errors: list[dict[str, str]] = []
    task_versions: dict[str, set[str]] = {}
    judge_versions: set[str] = set()
    futures: dict[
        concurrent.futures.Future[tuple[dict[str, Any], dict[str, Any], AdapterFingerprint]],
        tuple[ModelProfile, str],
    ] = {}
    matrix_workers = len(review_config.profiles) * 2
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=matrix_workers) as executor:
            for profile in review_config.profiles:
                for universe in ("repository", "isolated"):
                    futures[executor.submit(run_cell, profile, universe)] = (profile, universe)
            for future in concurrent.futures.as_completed(futures):
                profile, universe = futures[future]
                try:
                    cell, manifest_cell, adapter_fingerprint = future.result()
                except EvalError:
                    for outstanding in futures:
                        outstanding.cancel()
                    raise
                except Exception as exc:
                    cell_errors.append(
                        {
                            "profile_id": profile.id,
                            "universe": universe,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    continue
                cells.append(cell)
                task_versions.setdefault(profile.adapter, set()).add(
                    adapter_fingerprint.task_adapter_version
                )
                judge_versions.add(adapter_fingerprint.judge_adapter_version)
                local_manifest["cells"].append(manifest_cell)
                _write_json(local_root / "review.json", local_manifest)

        changed_task_versions = {
            adapter: versions for adapter, versions in task_versions.items() if len(versions) > 1
        }
        if changed_task_versions:
            raise EvalError(
                "Task harness version changed during the routine screen: "
                + json.dumps(
                    {
                        adapter: sorted(versions)
                        for adapter, versions in changed_task_versions.items()
                    },
                    sort_keys=True,
                )
            )
        if len(judge_versions) > 1:
            raise EvalError(
                "Judge harness version changed during the routine screen: "
                + ", ".join(sorted(judge_versions))
            )
        _assert_pinned_sources(
            review_config,
            skill_dir=skill_dir,
            candidate_dir=candidate_dir,
            spec=spec,
            current_digest=current_digest,
            candidate_digest=candidate_digest,
            eval_digest=eval_digest,
            task_manifest_digests=task_manifest_digests,
            judge_manifest_digest=judge_manifest_digest,
            groups_digest=groups_digest,
        )
    except Exception as exc:
        local_manifest["status"] = "failed"
        local_manifest["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(local_root / "review.json", local_manifest)
        raise
    aggregate = _aggregate_routine_screen(
        review_config.profiles,
        cells,
        discovery_changed=discovery_changed,
        protected_gate_ids=protected_gate_ids,
        cell_errors=cell_errors,
    )
    local_manifest["status"] = "completed"
    local_manifest["completed_at"] = datetime.now(UTC).isoformat()
    local_manifest["task_harness_versions"] = {
        adapter: next(iter(versions), None) for adapter, versions in sorted(task_versions.items())
    }
    local_manifest["judge_harness_version"] = next(iter(judge_versions), None)
    local_manifest["aggregate"] = aggregate
    local_manifest["cells"].sort(key=lambda item: (item["profile_id"], item["universe"]))
    _write_json(local_root / "review.json", local_manifest)
    review = {
        "schema_version": 1,
        "workflow": "routine",
        "orchestrator_version": ROUTINE_ORCHESTRATOR_VERSION,
        "local_review_id": local_root.name,
        "pinned_inputs": pinned_inputs,
        "coverage": {
            "universes": ["repository", "isolated"],
            "both_universes": True,
            "trigger_policy": "blocking-compact" if discovery_changed else "observational-omitted",
            "trigger_cases": list(selected_trigger),
            "behavior_cases": list(config.contract.behavior_cases),
            "trigger_repeats": 1,
            "behavior_repeats": 1,
            "held_back_cases_used": False,
        },
        "cells": sorted(cells, key=lambda item: (item["profile_id"], item["universe"])),
        "aggregate": aggregate,
    }
    return review, local_root


def validate_routine_escalation(
    path: Path,
    config: CapabilityReviewConfig,
) -> None:
    """Require an eligible routine screen pinned to the full escalation inputs."""
    payload = _object(_load_json(path, label="routine screen evidence"), location=str(path))
    if payload.get("workflow") != "routine" or payload.get("status") != "completed":
        raise EvalError("--escalate-from must reference a completed routine review.json")
    aggregate = payload.get("aggregate")
    if (
        not isinstance(aggregate, dict)
        or aggregate.get("outcome") != "eligible-for-escalation"
        or aggregate.get("report_only") is not True
        or aggregate.get("approval_possible") is not False
        or aggregate.get("automatic_promotion") is not False
    ):
        raise EvalError("--escalate-from routine outcome must be eligible-for-escalation")
    pinned = payload.get("pinned_inputs")
    if not isinstance(pinned, dict):
        raise EvalError("--escalate-from routine evidence is missing pinned inputs")
    profiles = pinned.get("profiles")
    required_profile_ids = [profile.id for profile in config.contract.profiles if profile.required]
    if (
        not isinstance(profiles, list)
        or not all(isinstance(profile_id, str) for profile_id in profiles)
        or set(profiles) != set(required_profile_ids)
        or len(profiles) != len(required_profile_ids)
    ):
        raise EvalError("--escalate-from routine evidence does not cover required profiles")
    cell_results = aggregate.get("cell_results")
    expected_cells = {
        (profile_id, universe) for profile_id in profiles for universe in ("repository", "isolated")
    }
    observed_cells = (
        {
            (item.get("profile_id"), item.get("universe"))
            for item in cell_results
            if isinstance(item, dict) and item.get("status") == "eligible-for-escalation"
        }
        if isinstance(cell_results, list)
        else set()
    )
    if not expected_cells or observed_cells != expected_cells:
        raise EvalError("--escalate-from routine evidence has incomplete eligible cells")

    repo_root = config.repo_root.resolve()
    skill_dir = resolve_skill(repo_root, config.skill)
    candidate_dir = resolve_candidate_skill(repo_root, config.candidate, skill_dir.name)
    spec = load_eval_spec(skill_dir, repo_root / "evals")
    required_profiles = tuple(profile for profile in config.contract.profiles if profile.required)
    task_manifest_digests, judge_manifest_digest = _harness_manifest_digests(
        repo_root,
        required_profiles,
        config.contract.judge_policy,
    )
    expected = {
        "skill": spec.skill_name,
        "current_digest_sha256": stable_digest(skill_dir, exclude=RUNTIME_EXCLUDED_NAMES),
        "candidate_digest_sha256": stable_digest(
            candidate_dir,
            exclude=RUNTIME_EXCLUDED_NAMES,
        ),
        "eval_digest_sha256": stable_digest(
            spec.path.parent,
            exclude=EVAL_DIGEST_EXCLUDED_NAMES,
        ),
        "profiles_digest_sha256": config.contract.digest_sha256,
        "case_groups_digest_sha256": _case_groups_digest(config.case_groups),
        "judge_policy_digest_sha256": canonical_digest(
            _review_policy_payload(spec, config.contract)
        ),
        "task_harness_manifest_digests_sha256": task_manifest_digests,
        "judge_harness_manifest_digest_sha256": judge_manifest_digest,
    }
    mismatches = [
        key for key, expected_value in expected.items() if pinned.get(key) != expected_value
    ]
    if mismatches:
        raise EvalError(
            "--escalate-from does not match current full-review inputs: " + ", ".join(mismatches)
        )


def _portable_source(path: Path | None, repo_root: Path, fallback: str) -> str | None:
    """Return a repository-relative source or a path-free placeholder."""
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return fallback


def _reproduction_argv(
    review: dict[str, Any],
    config: CapabilityReviewConfig,
) -> list[str]:
    """Build a path-safe command with digest assertions for every input."""
    pinned = review["pinned_inputs"]
    argv = [
        "python3",
        "scripts/review_skill_capability.py",
        "--skill",
        pinned["skill"],
        "--candidate",
        "${CANDIDATE_DIR}",
        "--profiles",
        _portable_source(
            config.profile_source,
            config.repo_root,
            "<model-profiles-json>",
        )
        or "<model-profiles-json>",
        "--trigger-repeats",
        str(config.trigger_repeats),
        "--behavior-repeats",
        str(config.behavior_repeats),
        "--activation-threshold",
        str(config.activation_threshold),
        "--sandbox",
        config.sandbox,
        "--expected-current-digest",
        pinned["current_digest_sha256"],
        "--expected-candidate-digest",
        pinned["candidate_digest_sha256"],
        "--expected-eval-digest",
        pinned["eval_digest_sha256"],
        "--expected-profiles-digest",
        pinned["profiles_digest_sha256"],
        "--expected-case-groups-digest",
        pinned["case_groups_digest_sha256"],
    ]
    case_source = _portable_source(
        config.case_group_source,
        config.repo_root,
        "<case-groups-json>",
    )
    if case_source is not None:
        argv.extend(["--case-groups", case_source])
    for profile in config.profiles:
        if not profile.required:
            argv.extend(["--observed-profile", profile.id])
    if len(config.universes) == 1:
        argv.extend(["--universe", config.universes[0]])
        if config.universe_limitation is not None:
            argv.extend(["--universe-limitation", config.universe_limitation.strip()])
    argv.append(
        "--allow-fixture-scripts" if config.allow_fixture_scripts else "--no-allow-fixture-scripts"
    )
    return argv


def build_durable_summary(
    review: dict[str, Any],
    config: CapabilityReviewConfig,
    *,
    disposition: str,
    reviewer: str,
    rationale: str,
) -> dict[str, Any]:
    """Build an allowlisted, deterministic, human-dispositioned export."""
    validate_durable_disposition(
        disposition=disposition,
        reviewer=reviewer,
        rationale=rationale,
    )
    for profile in config.profiles:
        _pinned_model(
            profile.model,
            adapter=profile.adapter,
            location=f"profile {profile.id} task model",
        )
    _pinned_model(
        config.contract.judge_policy.model,
        adapter=config.contract.judge_policy.adapter,
        location="judge policy model",
    )
    for cell in review.get("cells", []):
        if not isinstance(cell, dict):
            raise EvalError("Durable export requires object-valued profile cells")
        for key in (
            "task_adapter",
            "task_model_requested",
            "task_model_reported",
            "task_harness_version",
            "task_manifest_digest_sha256",
            "judge_adapter",
            "judge_model_requested",
            "judge_model_reported",
            "judge_harness_version",
            "judge_manifest_digest_sha256",
        ):
            if not isinstance(cell.get(key), str) or not cell[key].strip():
                raise EvalError(f"Durable export requires exact profile-cell evidence for {key}")

    evidence_identity = {
        "pinned_inputs": review["pinned_inputs"],
        "cells": review["cells"],
        "aggregate": review["aggregate"],
    }
    stable_review_id = (
        f"{review['pinned_inputs']['skill']}-{canonical_digest(evidence_identity)[:16]}"
    )
    summary = {
        "schema_version": DURABLE_SUMMARY_SCHEMA_VERSION,
        "review_id": stable_review_id,
        "orchestrator_version": review["orchestrator_version"],
        "skill": review["pinned_inputs"]["skill"],
        "inputs": {
            key: review["pinned_inputs"][key]
            for key in (
                "current_digest_sha256",
                "candidate_digest_sha256",
                "eval_digest_sha256",
                "eval_spec_digest_sha256",
                "profiles_digest_sha256",
                "case_groups_digest_sha256",
                "judge_policy_digest_sha256",
                "task_harness_manifest_digests_sha256",
                "judge_harness_manifest_digest_sha256",
                "harness_manifest_digest_sha256",
            )
        },
        "judge_policy": review["pinned_inputs"]["judge_policy"],
        "task_harnesses": review["task_harnesses"],
        "judge_harness": review["judge_harness"],
        "profiles": review["profiles"],
        "unselected_observed_profiles": review["unselected_observed_profiles"],
        "coverage": review["coverage"],
        "matrix": review["cells"],
        "aggregate": review["aggregate"],
        "reproduction": {
            "argv": _reproduction_argv(review, config),
            "environment": {
                "CANDIDATE_DIR": (
                    "Path to a candidate whose digest matches "
                    + review["pinned_inputs"]["candidate_digest_sha256"]
                )
            },
        },
        "confidence_limitations": _confidence_limitations(review),
        "human_review": {
            "reviewed": True,
            "reviewer": reviewer.strip(),
            "disposition": disposition,
            "rationale": rationale.strip(),
            "automatic_promotion": False,
        },
    }
    _validate_durable_summary(
        summary,
        forbidden_paths=(
            config.repo_root.resolve(),
            config.candidate.resolve(),
            config.output_root.resolve(),
        ),
    )
    return summary


def validate_durable_disposition(
    *,
    disposition: str | None,
    reviewer: str | None,
    rationale: str | None,
) -> None:
    """Validate human export fields at their first external boundary."""
    if disposition not in DISPOSITIONS:
        raise EvalError("--disposition must be one of: " + ", ".join(sorted(DISPOSITIONS)))
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise EvalError("--reviewer is required for durable export")
    if not isinstance(rationale, str) or not rationale.strip():
        raise EvalError("--disposition-rationale is required for durable export")
    if len(reviewer.strip()) > 200:
        raise EvalError("--reviewer must be at most 200 characters")
    if len(rationale.strip()) > 4000:
        raise EvalError("--disposition-rationale must be at most 4000 characters")
    for value, name in (
        (reviewer, "--reviewer"),
        (rationale, "--disposition-rationale"),
    ):
        if (
            UNIX_ABSOLUTE_PATH_RE.search(value)
            or WINDOWS_ABSOLUTE_PATH_RE.search(value)
            or FILE_ABSOLUTE_PATH_RE.search(value)
        ):
            raise EvalError(f"{name} must not contain an absolute path")


def _confidence_limitations(review: dict[str, Any]) -> list[str]:
    """Describe bounded conclusions and unresolved evidence."""
    limitations = [
        "Evidence applies only to the pinned eval, judge policy, runner, harness, and digests.",
        "Repeated model runs reduce but do not eliminate stochastic uncertainty.",
        "Selected profile evidence does not establish behavior in unselected harnesses.",
    ]
    coverage = review["coverage"]
    if not coverage["both_universes"]:
        limitations.append(
            "Only one skill universe was selected: " + str(coverage["single_universe_limitation"])
        )
    if not any(group["kind"] == "held-back" for group in coverage["case_groups"]):
        limitations.append(
            "No explicitly held-back case group was supplied; aggregate evidence is insufficient."
        )
    elif any(group["kind"] == "development" for group in coverage["case_groups"]):
        limitations.append(
            "Development and held-back groups are declarative process controls; "
            "whole-suite metrics do not prove held-back-only non-inferiority or "
            "measured group efficacy."
        )
    if review["aggregate"]["observed_failures"]:
        limitations.append(
            "Observed profile failures do not block but remain unresolved: "
            + ", ".join(review["aggregate"]["observed_failures"])
        )
    return limitations


def _walk(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    """Yield every nested value with its structural path."""
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


def _validate_durable_summary(
    summary: dict[str, Any],
    *,
    forbidden_paths: tuple[Path, ...],
) -> None:
    """Reject raw evidence fields and machine-specific absolute paths."""
    forbidden_text = tuple(str(path) for path in forbidden_paths)
    for path, value in _walk(summary):
        if path and path[-1].lower() in FORBIDDEN_EXPORT_KEYS:
            raise EvalError(
                "Durable summary contains forbidden raw-evidence field: " + ".".join(path)
            )
        if isinstance(value, str) and any(token and token in value for token in forbidden_text):
            raise EvalError("Durable summary contains a workspace path in field: " + ".".join(path))
        if isinstance(value, str) and (
            UNIX_ABSOLUTE_PATH_RE.search(value)
            or WINDOWS_ABSOLUTE_PATH_RE.search(value)
            or FILE_ABSOLUTE_PATH_RE.search(value)
        ):
            raise EvalError("Durable summary contains an absolute path in field: " + ".".join(path))


def _write_json(path: Path, value: object) -> None:
    """Write stable pretty JSON for local manifests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _markdown_value(value: object) -> str:
    """Render a compact deterministic Markdown scalar."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _markdown(summary: dict[str, Any]) -> str:
    """Render the bounded durable review as human-readable Markdown."""
    task_harnesses = ", ".join(
        f"`{item['adapter']}` `{item['version']}`" for item in summary["task_harnesses"]
    )
    judge_harness = summary["judge_harness"]
    lines = [
        f"# Capability review: {summary['skill']}",
        "",
        f"- Review ID: `{summary['review_id']}`",
        f"- Evidence verdict: **{summary['aggregate']['verdict']}**",
        f"- Human disposition: **{summary['human_review']['disposition']}**",
        f"- Reviewer: {summary['human_review']['reviewer']}",
        f"- Task harnesses: {task_harnesses}",
        f"- Judge harness: `{judge_harness['adapter']}` `{judge_harness['version']}`",
        (
            f"- Judge policy: `{summary['judge_policy']['judge_policy']['id']}` using "
            f"`{summary['judge_policy']['judge_policy']['adapter']}` / "
            f"`{summary['judge_policy']['judge_policy']['model']}` and "
            f"`{summary['judge_policy']['judge_policy']['protocol']}`"
        ),
        "- Automatic promotion: disabled",
        "",
        "## Pinned inputs",
        "",
        "| Input | SHA-256 |",
        "| --- | --- |",
    ]
    for key, value in summary["inputs"].items():
        rendered = (
            json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (dict, list))
            else str(value)
        )
        lines.append(f"| {key.removesuffix('_sha256').replace('_', ' ')} | `{rendered}` |")
    lines.extend(
        [
            "",
            "## Profile gates",
            "",
            "| Profile | Role | Status | Cell verdicts |",
            "| --- | --- | --- | --- |",
        ]
    )
    for profile in summary["aggregate"]["profile_results"]:
        verdicts = ", ".join(f"{cell['universe']}: {cell['verdict']}" for cell in profile["cells"])
        lines.append(f"| {profile['id']} | {profile['role']} | {profile['status']} | {verdicts} |")
    lines.extend(
        [
            "",
            "Observed failures are visible but do not block. Required profile failures or "
            "insufficient evidence block the aggregate verdict.",
            "",
            "## Coverage",
            "",
            "- Universes: " + ", ".join(summary["coverage"]["universes"]),
            (
                "- Single-universe limitation: "
                + str(summary["coverage"]["single_universe_limitation"])
                if not summary["coverage"]["both_universes"]
                else "- Both repository and isolated universes were run."
            ),
            (
                f"- Repeats: trigger {summary['coverage']['trigger_repeats']}, "
                f"behavior {summary['coverage']['behavior_repeats']}"
            ),
            "- Case groups: "
            + ", ".join(
                f"{group['id']} ({group['kind']})" for group in summary["coverage"]["case_groups"]
            ),
            "",
            "## Matrix",
            "",
            "| Profile | Role | Universe | Task harness | Requested / reported task model | "
            "Judge harness | Requested / reported judge model | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for cell in summary["matrix"]:
        lines.append(
            f"| {cell['profile_id']} | {cell['profile_role']} | {cell['universe']} | "
            f"`{cell['task_adapter']}` `{cell['task_harness_version']}` | "
            f"`{cell['task_model_requested']}` / `{cell['task_model_reported']}` | "
            f"`{cell['judge_adapter']}` `{cell['judge_harness_version']}` | "
            f"`{cell['judge_model_requested']}` / `{cell['judge_model_reported']}` | "
            f"{cell['verdict']} |"
        )
    lines.extend(
        [
            "",
            "## Baseline, Current, and Candidate metrics",
            "",
            "| Profile | Universe | Baseline behavior pass | Current behavior pass | "
            "Candidate behavior pass | Current trigger recall | Candidate trigger recall |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for cell in summary["matrix"]:
        metrics = cell["metrics"]
        lines.append(
            f"| {cell['profile_id']} | {cell['universe']} | "
            f"{_markdown_value(metrics['baseline']['behavior_checks']['pass_rate'])} | "
            f"{_markdown_value(metrics['current']['behavior_checks']['pass_rate'])} | "
            f"{_markdown_value(metrics['candidate']['behavior_checks']['pass_rate'])} | "
            f"{_markdown_value(metrics['triggering']['current']['recall'])} | "
            f"{_markdown_value(metrics['triggering']['candidate']['recall'])} |"
        )
    lines.extend(
        [
            "",
            "## Context footprint",
            "",
            "| Profile | Universe | Current description chars | Candidate description chars | "
            "Current body chars | Candidate body chars | Current package bytes | "
            "Candidate package bytes | Dynamic input-token reduction |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for cell in summary["matrix"]:
        footprint = cell["context_footprint"]
        comparison = cell["metrics"]["candidate_comparison"]
        lines.append(
            f"| {cell['profile_id']} | {cell['universe']} | "
            f"{_markdown_value(footprint['current']['description']['characters'])} | "
            f"{_markdown_value(footprint['candidate']['description']['characters'])} | "
            f"{_markdown_value(footprint['current']['skill_md_body']['characters'])} | "
            f"{_markdown_value(footprint['candidate']['skill_md_body']['characters'])} | "
            f"{_markdown_value(footprint['current']['runtime_package']['bytes'])} | "
            f"{_markdown_value(footprint['candidate']['runtime_package']['bytes'])} | "
            f"{_markdown_value(comparison['dynamic_input_token_reduction'])} |"
        )
    lines.extend(
        [
            "",
            "## Gate results",
            "",
            "| Profile | Universe | Dimension | Scope | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for cell in summary["matrix"]:
        for dimension_id, dimension in cell["gates"]["dimensions"].items():
            scope = (
                cell["gates"]["trigger_gate_scope"].get("trigger_gate_mode") or "blocking"
                if dimension_id == "triggering"
                else "blocking"
            )
            lines.append(
                f"| {cell['profile_id']} | {cell['universe']} | "
                f"{dimension_id} | {scope} | {dimension['status']} |"
            )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "Set `CANDIDATE_DIR` to a candidate matching the pinned digest, then run:",
            "",
            "```bash",
            shlex.join(summary["reproduction"]["argv"]),
            "```",
            "",
            "## Confidence limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in summary["confidence_limitations"])
    lines.extend(
        [
            "",
            "## Human-reviewed disposition",
            "",
            f"**{summary['human_review']['disposition']}** — "
            + summary["human_review"]["rationale"],
            "",
        ]
    )
    return "\n".join(lines)


def export_durable_summary(
    summary: dict[str, Any],
    *,
    repo_root: Path,
) -> tuple[Path, Path]:
    """Write bounded deterministic JSON and Markdown under the skill review directory."""
    _validate_durable_summary(summary, forbidden_paths=(repo_root.resolve(),))
    review_dir = repo_root.resolve() / "evals" / summary["skill"] / "reviews"
    json_path = review_dir / f"{summary['review_id']}.json"
    markdown_path = review_dir / f"{summary['review_id']}.md"
    json_text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_text = _markdown(summary)
    for label, content in (("JSON", json_text), ("Markdown", markdown_text)):
        if len(content.encode()) > MAX_EXPORT_BYTES:
            raise EvalError(f"Durable {label} summary exceeds the {MAX_EXPORT_BYTES}-byte bound")
    json_exists = json_path.exists()
    markdown_exists = markdown_path.exists()
    if json_exists != markdown_exists:
        raise EvalError(
            f"Refusing incomplete durable export for review {summary['review_id']}: "
            f"{json_path}, {markdown_path}"
        )
    if json_exists and (
        json_path.read_text(encoding="utf-8") != json_text
        or markdown_path.read_text(encoding="utf-8") != markdown_text
    ):
        raise EvalError(
            f"Refusing to overwrite different durable export for review {summary['review_id']}: "
            f"{json_path}, {markdown_path}"
        )
    review_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json_text, encoding="utf-8")
    markdown_path.write_text(markdown_text, encoding="utf-8")
    return json_path, markdown_path
