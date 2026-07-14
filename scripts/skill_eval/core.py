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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class EvalError(RuntimeError):
    """Raised for a user-actionable evaluator configuration error."""


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


def _case_id(value: object, *, location: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise EvalError(f"{location} id must be a string or integer")
    result = str(value).strip()
    if not result:
        raise EvalError(f"{location} id must not be empty")
    return result


def discover_repository_skills(repo_root: Path) -> tuple[Path, ...]:
    """Return skill packages deployable to Codex without entering eval fixtures."""
    skills_root = repo_root.resolve() / "skills"
    discovered: list[Path] = []
    portable = skills_root / "portable"
    if portable.is_dir():
        discovered.extend(
            path.parent.resolve() for path in portable.glob("*/SKILL.md")
        )
    codex_harness = skills_root / "harness" / "codex"
    if codex_harness.is_dir():
        discovered.extend(
            path.parent.resolve() for path in codex_harness.glob("*/SKILL.md")
        )
    return tuple(sorted(set(discovered), key=lambda path: str(path)))


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

    matches = [
        path for path in discover_repository_skills(repo_root) if path.name == selector
    ]
    if not matches:
        raise EvalError(
            f"No skill matches {selector!r}. Use a short name such as 'commit', "
            "a full id such as 'portable/commit', or a skill directory path."
        )
    if len(matches) > 1:
        display = ", ".join(str(path.relative_to(repo_root)) for path in matches)
        raise EvalError(f"Skill name {selector!r} is ambiguous: {display}")
    return matches[0]


def load_eval_spec(skill_dir: Path) -> EvalSpec:
    eval_path = skill_dir / "evals" / "evals.json"
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
            raise EvalError(
                f"behavior_evals[{index}].expected_behavior must be a non-empty string"
            )
        if not isinstance(fixtures, list) or not all(isinstance(x, str) for x in fixtures):
            raise EvalError(f"behavior_evals[{index}].fixtures must be a list of strings")
        if (
            not isinstance(checks, list)
            or not checks
            or not all(isinstance(x, str) and x.strip() for x in checks)
        ):
            raise EvalError(
                f"behavior_evals[{index}].checks must be a non-empty list of strings"
            )
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


def sanitized_skill_copy(skill_dir: Path, destination: Path) -> None:
    """Install Codex runtime content while withholding eval ground truth."""
    ignored = {"evals", "working", "__pycache__", ".git"}

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return ignored.intersection(names)

    shutil.copytree(skill_dir, destination, ignore=ignore)
    skill_md = destination / "SKILL.md"
    if skill_md.is_file():
        skill_md.write_text(
            _sanitize_codex_frontmatter(skill_md.read_text(encoding="utf-8")),
            encoding="utf-8",
        )


_CODEX_FRONTMATTER_KEYS = {"name", "description", "metadata"}


def _sanitize_codex_frontmatter(text: str) -> str:
    """Match the frontmatter filtering used by Codex copy deployments."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text

    kept: list[str] = []
    keeping = False
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if keeping:
                kept.append(line)
            continue
        if line[0].isspace():
            if keeping:
                kept.append(line)
            continue

        key = line.split(":", 1)[0].strip()
        keeping = key in _CODEX_FRONTMATTER_KEYS
        if keeping:
            kept.append(line)

    return "---\n" + "\n".join(kept).rstrip() + "\n" + text[end:]


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
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvalError(f"Fixture path must be skill-relative and may not traverse parents: {ref}")
    return candidate


def _fixture_target(relative: Path) -> Path:
    parts = relative.parts
    if len(parts) >= 4 and parts[:2] == ("evals", "fixtures"):
        return Path(*parts[3:])
    if len(parts) >= 3 and parts[:2] == ("evals", "fixtures"):
        return Path(parts[-1])
    return relative


def _copy_fixture_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise EvalError(f"Fixture collision at workspace path: {target}")
    shutil.copy2(source, target)


def materialize_fixtures(
    skill_dir: Path,
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
        candidates = [skill_dir / safe]
        if len(safe.parts) == 1:
            candidates.extend(
                [
                    skill_dir / "evals" / "fixtures" / safe,
                    skill_dir / "evals" / safe,
                    skill_dir / "evals" / f"{safe}.md",
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

        if source.is_file() and source.suffix.lower() == ".md" and source.parent == skill_dir / "evals":
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
            relative_to_skill = source.relative_to(skill_dir)
            destination_rel = _fixture_target(relative_to_skill)
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
        if len(data) <= preview_bytes:
            try:
                record["text"] = data.decode("utf-8")
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
        * math.sqrt(
            proportion * (1 - proportion) / total + z * z / (4 * total * total)
        )
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


def _grade_counts(grades: Iterable[dict[str, Any]]) -> dict[str, int | float | None]:
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


def summarize_behavior_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    skill_grades: list[dict[str, Any]] = []
    baseline_grades: list[dict[str, Any]] = []
    wins = regressions = ties = unknown_pairs = 0
    skill_case_passes = baseline_case_passes = 0
    graded_cases = 0
    case_summaries: list[dict[str, Any]] = []

    for result in results:
        skill = result.get("grades", {}).get("skill", [])
        baseline = result.get("grades", {}).get("baseline", [])
        skill_grades.extend(skill)
        baseline_grades.extend(baseline)
        if skill or baseline:
            graded_cases += 1
        skill_case_pass = bool(skill) and all(item.get("passed") is True for item in skill)
        baseline_case_pass = bool(baseline) and all(
            item.get("passed") is True for item in baseline
        )
        skill_case_passes += skill_case_pass
        baseline_case_passes += baseline_case_pass
        for skill_item, baseline_item in zip(skill, baseline, strict=False):
            pair = (skill_item.get("passed"), baseline_item.get("passed"))
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
                "skill_case_pass": skill_case_pass,
                "baseline_case_pass": baseline_case_pass,
                "skill_status": result["skill_run"]["status"],
                "baseline_status": result["baseline_run"]["status"],
                "skill_activated": result["skill_run"].get("activated"),
                "fixture_fidelity": result.get("fixture_fidelity"),
                "judge_status": result.get("judge", {}).get("status"),
            }
        )

    skill_counts = _grade_counts(skill_grades)
    baseline_counts = _grade_counts(baseline_grades)
    skill_rate = skill_counts["pass_rate"]
    baseline_rate = baseline_counts["pass_rate"]
    lift = (
        skill_rate - baseline_rate
        if isinstance(skill_rate, float) and isinstance(baseline_rate, float)
        else None
    )

    skill_runs = [result["skill_run"] for result in results]
    baseline_runs = [result["baseline_run"] for result in results]

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

    activation_completed = [run for run in skill_runs if run["status"] == "completed"]
    return {
        "skill": skill_counts,
        "baseline": baseline_counts,
        "absolute_lift": lift,
        "lift_percentage_points": lift * 100 if lift is not None else None,
        "paired_checks": {
            "skill_wins": wins,
            "regressions": regressions,
            "ties": ties,
            "unknown": unknown_pairs,
        },
        "case_pass_rate": {
            "skill": _rate(skill_case_passes, graded_cases),
            "baseline": _rate(baseline_case_passes, graded_cases),
            "graded_cases": graded_cases,
        },
        "behavior_activation_rate": _rate(
            sum(bool(run.get("activated")) for run in activation_completed),
            len(activation_completed),
        ),
        "efficiency": {
            "skill": efficiency(skill_runs),
            "baseline": efficiency(baseline_runs),
        },
        "cases": case_summaries,
    }


def efficacy_profile(
    trigger_summary: dict[str, Any] | None,
    behavior_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    activation = (
        trigger_summary.get("balanced_accuracy") if trigger_summary is not None else None
    )
    execution = (
        behavior_summary.get("skill", {}).get("pass_rate")
        if behavior_summary is not None
        else None
    )
    lift = behavior_summary.get("absolute_lift") if behavior_summary is not None else None
    coverage = (
        behavior_summary.get("skill", {}).get("evidence_coverage")
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
        "formula": "40% trigger balanced accuracy + 60% skill check pass rate; available components are renormalized",
        "note": "Incremental lift is reported separately so a strong general model is not mistaken for skill value.",
    }


def json_dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
