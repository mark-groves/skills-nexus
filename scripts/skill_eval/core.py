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
from typing import Any


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
class BehaviorCase:
    id: str
    prompt: str
    expected_behavior: str
    fixtures: tuple[str, ...]
    checks: tuple[str, ...]


@dataclass(frozen=True)
class EvalSpec:
    skill_name: str
    trigger_cases: tuple[TriggerCase, ...]
    behavior_cases: tuple[BehaviorCase, ...]
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
        if (
            not isinstance(checks, list)
            or not checks
            or not all(isinstance(x, str) and x.strip() for x in checks)
        ):
            raise EvalError(f"behavior_evals[{index}].checks must be a non-empty list of strings")
        behavior_cases.append(
            BehaviorCase(
                case_id,
                prompt,
                expected_behavior,
                tuple(fixtures),
                tuple(checks),
            )
        )

    if not trigger_cases and not behavior_cases:
        raise EvalError(f"No eval cases found in {eval_path}")
    return EvalSpec(name, tuple(trigger_cases), tuple(behavior_cases), eval_path)


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
