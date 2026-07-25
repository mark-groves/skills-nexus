"""Versioned component selectors and fail-closed backward elimination."""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from skill_eval.core import (
    RUNTIME_EXCLUDED_NAMES,
    EvalError,
    measure_static_footprint,
    resolve_skill,
    runtime_skill_copy,
    stable_digest,
)

from skill_review.core import CapabilityReviewConfig, canonical_digest

COMPONENT_SCHEMA_VERSION = 1
ABLATION_RECORD_SCHEMA_VERSION = 1
ABLATION_ORCHESTRATOR_VERSION = "component-ablation-v1"
MAX_COMPONENTS = 128
HEADING_RE = re.compile(r"^(#{2,6})[ \t]+(.+?)[ \t]*$")
FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,}).*$")
SAFE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
EVAL_DIGEST_EXCLUDED_NAMES = frozenset({"reviews", "working", "__pycache__"})

CapabilityRunner = Callable[[CapabilityReviewConfig], tuple[dict[str, Any], Path]]


@dataclass(frozen=True)
class Component:
    """One exact repository-owned section selector."""

    id: str
    source: str
    heading: str
    class_name: str
    protected: bool

    def as_dict(self) -> dict[str, Any]:
        """Return the normalized metadata representation."""
        return {
            "id": self.id,
            "source": self.source,
            "heading": self.heading,
            "class": self.class_name,
            "protected": self.protected,
        }


@dataclass(frozen=True)
class SectionSpan:
    """An exact byte-preserving Markdown section span."""

    component: Component
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ComponentContract:
    """Validated component metadata pinned to one runtime package."""

    schema_version: int
    components: tuple[Component, ...]
    digest_sha256: str
    spans: dict[str, SectionSpan]

    def as_dict(self) -> dict[str, Any]:
        """Return the normalized contract representation."""
        return {
            "schema_version": self.schema_version,
            "components": [component.as_dict() for component in self.components],
        }


@dataclass(frozen=True)
class ComponentAblationConfig:
    """Inputs for one local-only greedy component review."""

    review: CapabilityReviewConfig
    components_source: Path
    output_root: Path

    def __post_init__(self) -> None:
        """Require both universes because peer coverage is not model capability."""
        if self.review.universes != ("repository", "isolated"):
            raise EvalError("Component ablation requires both repository and isolated universes")


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvalError(f"Missing component metadata: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise EvalError(f"Unable to read component metadata {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvalError(f"Invalid JSON in component metadata {path}: {exc}") from exc


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
    match = HEADING_RE.fullmatch(line.rstrip("\r\n"))
    return len(match.group(1)) if match is not None else None


def _markdown_heading_levels(lines: list[str]) -> list[int | None]:
    """Identify supported headings while ignoring fenced code blocks."""
    levels: list[int | None] = []
    fence_character: str | None = None
    fence_length = 0
    for line in lines:
        stripped = line.rstrip("\r\n")
        fence = FENCE_RE.fullmatch(stripped)
        if fence_character is None:
            if fence is not None:
                marker = fence.group(1)
                fence_character = marker[0]
                fence_length = len(marker)
                levels.append(None)
                continue
            levels.append(_heading_level(line))
            continue
        closing = re.fullmatch(
            rf"[ ]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
            stripped,
        )
        if closing is not None:
            fence_character = None
            fence_length = 0
        levels.append(None)
    return levels


def _resolve_span(source: Path, component: Component) -> SectionSpan:
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EvalError(f"Component source must be UTF-8: {source}") from exc
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
    if level is None:
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
    """Load metadata and resolve every selector against the complete current skill."""
    if path.is_symlink():
        raise EvalError(f"Component metadata must not be a symlink: {path}")
    payload = _load_json(path)
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


def validate_component_metadata_source(
    repo_root: Path,
    skill_dir: Path,
    components_source: Path,
) -> Path:
    """Require repository-owned metadata and return its complete eval directory."""
    eval_dir = (repo_root.resolve() / "evals" / skill_dir.name).resolve()
    try:
        components_source.resolve().relative_to(eval_dir)
    except ValueError as exc:
        raise EvalError(
            "Component metadata must remain under the selected skill's repository eval directory"
        ) from exc
    return eval_dir


def create_component_candidate(
    skill_dir: Path,
    destination: Path,
    contract: ComponentContract,
    removed_ids: set[str],
) -> str:
    """Create a clean runtime candidate with exact declared sections removed."""
    protected = {
        component.id
        for component in contract.components
        if component.protected and component.id in removed_ids
    }
    if protected:
        raise EvalError("Protected components cannot be removed: " + ", ".join(sorted(protected)))
    unknown = sorted(removed_ids - set(contract.spans))
    if unknown:
        raise EvalError("Unknown component ids requested for removal: " + ", ".join(unknown))

    runtime_skill_copy(skill_dir, destination)
    by_source: dict[str, list[SectionSpan]] = {}
    for component_id in removed_ids:
        span = contract.spans[component_id]
        by_source.setdefault(span.component.source, []).append(span)
    for source, spans in by_source.items():
        source_path = skill_dir / source
        target_path = destination / source
        text = source_path.read_text(encoding="utf-8")
        for span in sorted(spans, key=lambda item: item.start, reverse=True):
            if text[span.start : span.end] != span.text:
                raise EvalError(
                    f"Component {span.component.id!r} source changed before candidate creation"
                )
            text = text[: span.start] + text[span.end :]
        target_path.write_text(text, encoding="utf-8")
    digest = stable_digest(destination, exclude=RUNTIME_EXCLUDED_NAMES)
    measure_static_footprint(destination, digest)
    return digest


def _static_savings(
    prior: dict[str, Any],
    candidate: dict[str, Any],
    complete: dict[str, Any],
) -> dict[str, dict[str, int]]:
    fields = {
        "description": ("characters", "utf8_bytes"),
        "skill_md_body": ("characters", "utf8_bytes"),
        "runtime_package": ("file_count", "bytes"),
    }

    def reductions(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
        result: dict[str, int] = {}
        for section, names in fields.items():
            for name in names:
                result[f"{section}_{name}"] = int(left[section][name]) - int(right[section][name])
        return result

    return {
        "incremental": reductions(prior, candidate),
        "cumulative": reductions(complete, candidate),
    }


def _hard_regressions(cell: dict[str, Any]) -> list[str]:
    regressions: list[str] = []
    gates = cell.get("gates")
    if not isinstance(gates, dict):
        raise EvalError("Capability review cell gates must be an object")
    dimensions = gates.get("dimensions")
    if not isinstance(dimensions, dict):
        raise EvalError("Capability review cell gate dimensions must be an object")
    for dimension, value in dimensions.items():
        if not isinstance(value, dict):
            raise EvalError("Capability review gate dimension must be an object")
        supplied_gates = value.get("gates")
        if not isinstance(supplied_gates, list):
            raise EvalError("Capability review dimension gates must be a list")
        for gate in supplied_gates:
            if not isinstance(gate, dict):
                raise EvalError("Capability review gates must be objects")
            if gate.get("hard") is True and gate.get("status") != "pass":
                regressions.append(f"{dimension}:{gate.get('id')}")
    metrics = cell.get("metrics")
    if not isinstance(metrics, dict):
        raise EvalError("Capability review cell metrics must be an object")
    comparison = metrics.get("candidate_comparison")
    if not isinstance(comparison, dict):
        raise EvalError("Capability review candidate comparison must be an object")
    paired = comparison.get("paired_checks")
    if not isinstance(paired, dict):
        raise EvalError("Capability review paired checks must be an object")
    paired_regressions = paired.get("regressions")
    if not isinstance(paired_regressions, int) or isinstance(paired_regressions, bool):
        raise EvalError("Capability review paired-check regressions must be an integer")
    if paired_regressions > 0:
        regressions.append(f"paired-checks:{paired_regressions}")
    return regressions


def _review_evidence(
    review: dict[str, Any],
    config: CapabilityReviewConfig,
) -> dict[str, Any]:
    """Reduce one capability review to bounded decision evidence."""
    cells = review.get("cells")
    aggregate = review.get("aggregate")
    if not isinstance(cells, list) or not isinstance(aggregate, dict):
        raise EvalError("Capability runner returned an incomplete review")
    universes = {cell.get("universe") for cell in cells if isinstance(cell, dict)}
    if universes != set(config.universes):
        raise EvalError(
            "Capability review did not report both repository and isolated universe results"
        )
    required_profiles = {profile.id for profile in config.profiles if profile.required}
    observed_required = {
        cell.get("profile_id")
        for cell in cells
        if isinstance(cell, dict) and cell.get("profile_role") == "required"
    }
    if observed_required != required_profiles:
        raise EvalError("Capability review omitted a required model profile")

    quality: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    universe_results: dict[str, list[dict[str, Any]]] = {
        "repository": [],
        "isolated": [],
    }
    material_uncertainty: list[str] = []
    observed_uncertainty: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise EvalError("Capability review cells must be objects")
        metrics = cell.get("metrics")
        if not isinstance(metrics, dict):
            raise EvalError("Capability review cell metrics must be an object")
        comparison = metrics.get("candidate_comparison")
        if not isinstance(comparison, dict):
            raise EvalError("Capability review candidate comparison must be an object")
        delta = comparison.get("candidate_minus_current_quality")
        quality_item = {
            "profile_id": cell.get("profile_id"),
            "profile_role": cell.get("profile_role"),
            "universe": cell.get("universe"),
            "candidate_minus_current": delta,
        }
        quality.append(quality_item)
        hard = _hard_regressions(cell)
        if hard:
            regressions.append({**quality_item, "gates": hard})
        unknown_checks = (
            comparison.get("paired_checks", {}).get("unknown")
            if isinstance(comparison, dict) and isinstance(comparison.get("paired_checks"), dict)
            else None
        )
        reasons = []
        if not isinstance(delta, (int, float)) or isinstance(delta, bool):
            reasons.append("quality delta is unavailable")
        if isinstance(unknown_checks, int) and unknown_checks > 0:
            reasons.append(f"{unknown_checks} paired checks are unknown")
        if cell.get("verdict") == "insufficient-evidence":
            reasons.append("cell verdict is insufficient-evidence")
        target = (
            material_uncertainty if cell.get("profile_role") == "required" else observed_uncertainty
        )
        target.extend(
            f"{cell.get('profile_id')}/{cell.get('universe')}: {reason}" for reason in reasons
        )
        universe = cell.get("universe")
        if universe not in universe_results:
            raise EvalError(f"Unexpected capability-review universe: {universe!r}")
        universe_results[universe].append(
            {
                "profile_id": cell.get("profile_id"),
                "profile_role": cell.get("profile_role"),
                "verdict": cell.get("verdict"),
                "quality_delta": delta,
                "hard_regressions": hard,
                "gates": cell.get("gates"),
            }
        )

    verdict = aggregate.get("verdict")
    if verdict not in {"approved", "rejected", "insufficient-evidence"}:
        raise EvalError(f"Capability review returned an unknown verdict: {verdict!r}")
    return {
        "verdict": verdict,
        "quality_delta": quality,
        "hard_regressions": regressions,
        "gate_outcome": aggregate,
        "uncertainty": {
            "material": bool(material_uncertainty),
            "required_reasons": material_uncertainty,
            "observed_reasons": observed_uncertainty,
        },
        "universe_results": universe_results,
    }


def _selection_score(trial: dict[str, Any]) -> tuple[float, int, str]:
    """Rank safe trials by worst quality, savings, then stable component ID."""
    required_deltas = [
        item["candidate_minus_current"]
        for item in trial["quality_delta"]
        if item["profile_role"] == "required"
    ]
    if not required_deltas:
        raise EvalError("Component ablation requires required-profile quality evidence")
    worst_quality = min(float(value) for value in required_deltas)
    savings = trial["static_savings"]["incremental"]["runtime_package_bytes"]
    return (worst_quality, savings, trial["component_id"])


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_pinned(
    config: ComponentAblationConfig,
    skill_dir: Path,
    eval_dir: Path,
    *,
    current_digest: str,
    components_digest: str,
    eval_digest: str,
) -> None:
    observed_current = stable_digest(skill_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    if observed_current != current_digest:
        raise EvalError(
            "Current runtime package changed during component ablation: "
            f"expected {current_digest}, observed {observed_current}"
        )
    observed_contract = load_component_contract(config.components_source, skill_dir)
    if observed_contract.digest_sha256 != components_digest:
        raise EvalError(
            "Component metadata changed during component ablation: "
            f"expected {components_digest}, observed {observed_contract.digest_sha256}"
        )
    observed_eval = stable_digest(
        eval_dir,
        exclude=EVAL_DIGEST_EXCLUDED_NAMES,
    )
    if observed_eval != eval_digest:
        raise EvalError(
            "Evaluation bundle changed during component ablation: "
            f"expected {eval_digest}, observed {observed_eval}"
        )


def _candidate_review(
    *,
    config: ComponentAblationConfig,
    capability_runner: CapabilityRunner,
    contract: ComponentContract,
    skill_dir: Path,
    removed_ids: set[str],
    prior_footprint: dict[str, Any],
    complete_footprint: dict[str, Any],
    review_root: Path,
    candidate_parent: Path,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="candidate-", dir=candidate_parent) as temp_dir:
        candidate_dir = Path(temp_dir) / skill_dir.name
        candidate_digest = create_component_candidate(
            skill_dir,
            candidate_dir,
            contract,
            removed_ids,
        )
        candidate_footprint = measure_static_footprint(candidate_dir, candidate_digest)
        review_config = replace(
            config.review,
            candidate=candidate_dir,
            output_root=review_root,
        )
        review, _local_review = capability_runner(review_config)
        evidence = _review_evidence(review, review_config)
        evidence["static_savings"] = _static_savings(
            prior_footprint,
            candidate_footprint,
            complete_footprint,
        )
        return candidate_digest, candidate_footprint, evidence


def run_component_ablation(
    config: ComponentAblationConfig,
    capability_runner: CapabilityRunner,
) -> tuple[dict[str, Any], Path]:
    """Greedily remove safe components and rerun the final combination from scratch."""
    repo_root = config.review.repo_root.resolve()
    skill_dir = resolve_skill(repo_root, config.review.skill)
    eval_dir = validate_component_metadata_source(
        repo_root,
        skill_dir,
        config.components_source,
    )
    output_root = config.output_root.resolve()
    try:
        output_relative = output_root.relative_to(repo_root)
    except ValueError:
        output_relative = None
    if output_relative is not None and (
        not output_relative.parts or output_relative.parts[0] != ".skill-evals"
    ):
        raise EvalError(
            "A repository-local --output-root must remain under the ignored .skill-evals root"
        )
    contract = load_component_contract(config.components_source, skill_dir)
    current_digest = stable_digest(skill_dir, exclude=RUNTIME_EXCLUDED_NAMES)
    eval_digest = stable_digest(
        eval_dir,
        exclude=EVAL_DIGEST_EXCLUDED_NAMES,
    )
    case_groups_digest = canonical_digest([group.as_dict() for group in config.review.case_groups])
    complete_footprint = measure_static_footprint(skill_dir, current_digest)
    input_digest = canonical_digest(
        {
            "skill": skill_dir.name,
            "current_digest_sha256": current_digest,
            "components_digest_sha256": contract.digest_sha256,
            "eval_digest_sha256": eval_digest,
            "profiles_digest_sha256": config.review.contract.digest_sha256,
            "case_groups_digest_sha256": case_groups_digest,
            "universes": list(config.review.universes),
        }
    )
    timestamp = datetime.now(UTC)
    local_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{input_digest[:12]}"
    local_root = config.output_root.resolve() / skill_dir.name / "component-ablations" / local_id
    suffix = 1
    while local_root.exists():
        local_root = local_root.with_name(f"{local_id}-{suffix}")
        suffix += 1
    local_root.mkdir(parents=True)
    candidate_parent = local_root / "temporary-candidates"
    candidate_parent.mkdir()
    record_path = local_root / "decision.json"
    component_states = [
        {
            **component.as_dict(),
            "status": "skipped-protected" if component.protected else "pending",
        }
        for component in contract.components
    ]
    record: dict[str, Any] = {
        "schema_version": ABLATION_RECORD_SCHEMA_VERSION,
        "orchestrator_version": ABLATION_ORCHESTRATOR_VERSION,
        "status": "running",
        "started_at": timestamp.isoformat(),
        "automatic_runtime_change": False,
        "inputs": {
            "skill": skill_dir.name,
            "current_digest_sha256": current_digest,
            "components_digest_sha256": contract.digest_sha256,
            "eval_digest_sha256": eval_digest,
            "profiles_digest_sha256": config.review.contract.digest_sha256,
            "case_groups_digest_sha256": case_groups_digest,
            "universes": list(config.review.universes),
        },
        "components": component_states,
        "rounds": [],
        "accepted_steps": [],
        "final_verification": None,
    }
    _write_record(record_path, record)

    removed_ids: set[str] = set()
    remaining = [component for component in contract.components if not component.protected]
    prior_digest = current_digest
    prior_footprint = complete_footprint
    try:
        round_number = 0
        while remaining:
            round_number += 1
            trials: list[dict[str, Any]] = []
            eligible: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for component in remaining:
                _assert_pinned(
                    config,
                    skill_dir,
                    eval_dir,
                    current_digest=current_digest,
                    components_digest=contract.digest_sha256,
                    eval_digest=eval_digest,
                )
                candidate_removed = {*removed_ids, component.id}
                try:
                    candidate_digest, candidate_footprint, evidence = _candidate_review(
                        config=config,
                        capability_runner=capability_runner,
                        contract=contract,
                        skill_dir=skill_dir,
                        removed_ids=candidate_removed,
                        prior_footprint=prior_footprint,
                        complete_footprint=complete_footprint,
                        review_root=(
                            local_root
                            / "capability-reviews"
                            / f"round-{round_number:03d}"
                            / component.id
                        ),
                        candidate_parent=candidate_parent,
                    )
                    trial = {
                        "component_id": component.id,
                        "prior_digest_sha256": prior_digest,
                        "candidate_digest_sha256": candidate_digest,
                        **evidence,
                    }
                    if (
                        evidence["verdict"] == "approved"
                        and not evidence["uncertainty"]["material"]
                    ):
                        trial["decision"] = "eligible"
                        eligible.append((trial, candidate_footprint))
                    else:
                        trial["decision"] = (
                            "insufficient-evidence"
                            if evidence["verdict"] == "insufficient-evidence"
                            or evidence["uncertainty"]["material"]
                            else "rejected"
                        )
                except EvalError as exc:
                    trial = {
                        "component_id": component.id,
                        "prior_digest_sha256": prior_digest,
                        "candidate_digest_sha256": None,
                        "decision": "invalid-candidate",
                        "error": str(exc),
                        "uncertainty": {
                            "material": True,
                            "required_reasons": ["candidate validation failed"],
                            "observed_reasons": [],
                        },
                    }
                trials.append(trial)
                record["rounds"].append(
                    {
                        "round": round_number,
                        "status": "running",
                        "trials": list(trials),
                    }
                )
                # Replace the transient progress entry rather than duplicating the round.
                if len(record["rounds"]) > 1 and record["rounds"][-2]["round"] == round_number:
                    record["rounds"].pop(-2)
                _write_record(record_path, record)

            if not eligible:
                record["rounds"][-1]["status"] = "no-safe-removal"
                break

            selected, selected_footprint = max(
                eligible,
                key=lambda item: _selection_score(item[0]),
            )
            selected["decision"] = "accepted"
            for trial in trials:
                if trial is not selected and trial.get("decision") == "eligible":
                    trial["decision"] = "not-selected"
            record["rounds"][-1] = {
                "round": round_number,
                "status": "accepted",
                "selected_component_id": selected["component_id"],
                "trials": trials,
            }
            accepted_step = {
                "round": round_number,
                **selected,
            }
            record["accepted_steps"].append(accepted_step)
            removed_ids.add(selected["component_id"])
            prior_digest = selected["candidate_digest_sha256"]
            prior_footprint = selected_footprint
            remaining = [
                component for component in remaining if component.id != selected["component_id"]
            ]
            for state in component_states:
                if state["id"] == selected["component_id"]:
                    state["status"] = "accepted-provisionally"
            _write_record(record_path, record)

        _assert_pinned(
            config,
            skill_dir,
            eval_dir,
            current_digest=current_digest,
            components_digest=contract.digest_sha256,
            eval_digest=eval_digest,
        )
        final_digest, _final_footprint, final_evidence = _candidate_review(
            config=config,
            capability_runner=capability_runner,
            contract=contract,
            skill_dir=skill_dir,
            removed_ids=removed_ids,
            prior_footprint=complete_footprint,
            complete_footprint=complete_footprint,
            review_root=local_root / "capability-reviews" / "final-combined",
            candidate_parent=candidate_parent,
        )
        final_approved = (
            bool(removed_ids)
            and final_evidence["verdict"] == "approved"
            and not final_evidence["uncertainty"]["material"]
        )
        record["final_verification"] = {
            "rerun_from_scratch": True,
            "removed_component_ids": sorted(removed_ids),
            "candidate_digest_sha256": final_digest,
            **final_evidence,
            "approved_for_human_review": final_approved,
        }
        record["outcome"] = "propose-reduction" if final_approved else "retain-current"
        for state in component_states:
            if state["protected"]:
                continue
            if state["id"] in removed_ids:
                state["status"] = "final-approved" if final_approved else "final-rejected"
            elif state["status"] == "pending":
                state["status"] = "retained"
        record["status"] = "completed"
        record["completed_at"] = datetime.now(UTC).isoformat()
        _write_record(record_path, record)
    except BaseException as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["completed_at"] = datetime.now(UTC).isoformat()
        _write_record(record_path, record)
        raise
    finally:
        try:
            candidate_parent.rmdir()
        except OSError:
            pass

    return record, local_root
