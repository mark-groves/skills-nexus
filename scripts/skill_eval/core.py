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
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class EvalError(RuntimeError):
    """Raised for a user-actionable evaluator configuration error."""


RUNTIME_EXCLUDED_NAMES = frozenset({"evals", "working", "__pycache__", ".git"})


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
    excluded = set(exclude)
    if path.is_file():
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for item in sorted(path.rglob("*"), key=lambda entry: entry.as_posix()):
        relative = item.relative_to(path)
        if any(part in excluded for part in relative.parts):
            continue
        if not item.is_file() or item.is_symlink():
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


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
    if len(conditions) != 2:
        raise EvalError("paired behavior summaries require exactly two conditions")
    primary, comparison = conditions
    grades_by_condition: dict[str, list[dict[str, Any]]] = {
        condition.id: [] for condition in conditions
    }
    wins = regressions = ties = unknown_pairs = 0
    case_passes = {condition.id: 0 for condition in conditions}
    graded_cases = 0
    case_summaries: list[dict[str, Any]] = []

    for result in results:
        result_grades = result.get("grades", {})
        primary_grades = result_grades.get(primary.id, [])
        comparison_grades = result_grades.get(comparison.id, [])
        grades_by_condition[primary.id].extend(primary_grades)
        grades_by_condition[comparison.id].extend(comparison_grades)
        if primary_grades or comparison_grades:
            graded_cases += 1
        condition_case_passes = {
            primary.id: bool(primary_grades)
            and all(item.get("passed") is True for item in primary_grades),
            comparison.id: bool(comparison_grades)
            and all(item.get("passed") is True for item in comparison_grades),
        }
        for condition in conditions:
            case_passes[condition.id] += condition_case_passes[condition.id]
        for primary_item, comparison_item in zip(
            primary_grades,
            comparison_grades,
            strict=False,
        ):
            pair = (primary_item.get("passed"), comparison_item.get("passed"))
            if pair == (True, False):
                wins += 1
            elif pair == (False, True):
                regressions += 1
            elif None in pair:
                unknown_pairs += 1
            else:
                ties += 1
        case_summaries.append(
            {
                "id": result["case_id"],
                "repeat": result["repeat"],
                f"{primary.id}_case_pass": condition_case_passes[primary.id],
                f"{comparison.id}_case_pass": condition_case_passes[comparison.id],
                f"{primary.id}_status": result[f"{primary.id}_run"]["status"],
                f"{comparison.id}_status": result[f"{comparison.id}_run"]["status"],
                f"{primary.id}_activated": result[f"{primary.id}_run"].get("activated"),
                "fixture_fidelity": result.get("fixture_fidelity"),
                "judge_status": result.get("judge", {}).get("status"),
            }
        )

    counts = {
        condition.id: _grade_counts(grades_by_condition[condition.id]) for condition in conditions
    }
    primary_rate = counts[primary.id]["pass_rate"]
    comparison_rate = counts[comparison.id]["pass_rate"]
    lift = (
        primary_rate - comparison_rate
        if isinstance(primary_rate, float) and isinstance(comparison_rate, float)
        else None
    )

    runs_by_condition = {
        condition.id: [result[f"{condition.id}_run"] for result in results]
        for condition in conditions
    }

    def efficiency(runs: list[dict[str, Any]]) -> dict[str, Any]:
        completed = [run for run in runs if run["status"] == "completed"]
        durations = [float(run["duration_seconds"]) for run in completed]
        tokens = [
            int(run.get("usage", {}).get("input_tokens", 0))
            + int(run.get("usage", {}).get("output_tokens", 0))
            for run in completed
        ]
        return {
            "completed_runs": len(completed),
            "errors": len(runs) - len(completed),
            "median_duration_seconds": statistics.median(durations) if durations else None,
            "total_tokens": sum(tokens),
            "median_tokens": statistics.median(tokens) if tokens else None,
            "tool_calls": sum(int(run.get("tool_calls", 0)) for run in completed),
        }

    activation_completed = [
        run for run in runs_by_condition[primary.id] if run["status"] == "completed"
    ]
    return {
        **counts,
        "absolute_lift": lift,
        "lift_percentage_points": lift * 100 if lift is not None else None,
        "paired_checks": {
            "skill_wins": wins,
            "regressions": regressions,
            "ties": ties,
            "unknown": unknown_pairs,
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
