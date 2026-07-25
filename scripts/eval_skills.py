#!/usr/bin/env python3
"""Execute trigger and behavior evals for one repository skill."""

from __future__ import annotations

import argparse
import concurrent.futures
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, TypeVar

from skill_eval.codex_runner import CodexRunner
from skill_eval.core import (
    BehaviorCase,
    EvalError,
    EvaluationCondition,
    TriggerCase,
    candidate_evaluation_conditions,
    default_evaluation_conditions,
    discover_repository_skills,
    efficacy_profile,
    initialize_fixture_repository,
    json_dump,
    load_eval_spec,
    materialize_fixtures,
    resolve_candidate_skill,
    resolve_skill,
    run_fixture_setups,
    snapshot_candidate_skill,
    snapshot_workspace,
    stable_digest,
    summarize_behavior_results,
    summarize_trigger_results,
    validate_candidate_separation,
)
from skill_eval.report import write_reports

REPO_ROOT = Path(__file__).resolve().parents[1]
T = TypeVar("T", TriggerCase, BehaviorCase)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure skill activation, behavior, incremental lift, and execution cost in "
            "fresh isolated Codex contexts."
        )
    )
    parser.add_argument("--skill", required=True, help="Short name, full skill id, or directory")
    parser.add_argument(
        "--candidate",
        type=Path,
        help=(
            "Publishable candidate skill directory with the same logical skill identity; "
            "repository-relative paths resolve from --repo-root"
        ),
    )
    parser.add_argument("--suite", choices=("all", "trigger", "behavior"), default="all")
    parser.add_argument("--trigger-case", action="append", default=[], metavar="ID")
    parser.add_argument("--behavior-case", action="append", default=[], metavar="ID")
    parser.add_argument("--max-trigger-cases", type=int)
    parser.add_argument("--max-behavior-cases", type=int)
    parser.add_argument("--trigger-repeats", type=int, default=1)
    parser.add_argument("--behavior-repeats", type=int, default=1)
    parser.add_argument("--activation-threshold", type=float, default=0.5)
    parser.add_argument("--jobs", type=int, default=2, help="Maximum concurrent agent turns")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds per agent turn")
    parser.add_argument("--model", help="Codex model for task runs")
    parser.add_argument("--judge-model", help="Codex model for grading; defaults to --model")
    parser.add_argument("--codex-binary", default="codex")
    parser.add_argument(
        "--skill-universe",
        choices=("repository", "isolated"),
        default="repository",
        help=(
            "Install clean runtime copies of repository peers in both conditions, or evaluate the selected "
            "skill alone"
        ),
    )
    parser.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
        help="Sandbox for behavior task runs; trigger and judge turns are always read-only",
    )
    parser.add_argument(
        "--allow-fixture-scripts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run trusted eval suite fixture setup scripts in isolated workspaces",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".skill-evals",
        help="Root for reports and raw evidence",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Validate selection and print the run/cost shape without invoking an agent",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        metavar="PERCENT",
        help="Exit 2 when absolute efficacy is below this percentage",
    )
    return parser


def _positive_int(value: int | None, name: str) -> None:
    if value is not None and value <= 0:
        raise EvalError(f"{name} must be greater than zero")


def _select_cases(
    cases: tuple[T, ...],
    requested: list[str],
    maximum: int | None,
    *,
    kind: str,
) -> tuple[T, ...]:
    by_id = {case.id: case for case in cases}
    if requested:
        duplicates = sorted(case_id for case_id in set(requested) if requested.count(case_id) > 1)
        if duplicates:
            raise EvalError(f"Duplicate {kind} case id(s): {', '.join(duplicates)}")
        unknown = [case_id for case_id in requested if case_id not in by_id]
        if unknown:
            raise EvalError(f"Unknown {kind} case id(s): {', '.join(unknown)}")
        selected = tuple(by_id[case_id] for case_id in requested)
    else:
        selected = cases
    return selected[:maximum] if maximum is not None else selected


def _behavior_prompt(case: BehaviorCase) -> str:
    if case.fixtures:
        context = (
            "Work only inside the current workspace. Input fixture files are already present. "
            "If .eval/fixtures contains scenario notes, treat only their repository-state "
            "description as authoritative. "
        )
    else:
        context = (
            "Answer the user's task normally. If the task requires files or commands, work only "
            "inside the current workspace. "
        )
    return (
        context
        + "Put any created deliverables in the current workspace and report their exact paths."
        + "\n\nTask:\n"
        + case.prompt
    )


def _git_metadata(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str | None:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("symbolic-ref", "--quiet", "--short", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def _fixture_fidelity(
    records: list[dict[str, Any]],
    setups: list[dict[str, Any]],
    repository: dict[str, Any],
) -> str:
    if any(record["status"] == "missing" for record in records):
        return "missing"
    if not repository.get("ok", False):
        return "setup-failed"
    if any(result["exit_code"] != 0 for result in setups):
        return "setup-failed"
    if any(record["status"] == "degraded" for record in records):
        return "degraded"
    if any(record["mode"] == "description_only" for record in records):
        return "description-only"
    if any(record["mode"] == "executable" for record in records):
        return "executable"
    return "files" if records else "none"


def _fixture_error_run(
    *,
    case_id: str,
    repeat: int,
    condition: EvaluationCondition,
    run_dir: Path,
    fidelity: str,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "status": "fixture_error",
        "exit_code": None,
        "duration_seconds": 0.0,
        "usage": {},
        "tool_calls": 0,
        "activated": False,
        "final_response": "",
        "case_type": "behavior",
        "case_id": case_id,
        "repeat": repeat,
        "condition": condition.id,
        "workspace": "",
        "artifact_delta": {"created": [], "modified": [], "deleted": []},
        "git": {"available": False},
        "error": f"Fixture fidelity is {fidelity}; task run was withheld",
    }
    json_dump(run_dir / "run.json", result)
    return result


def _unknown_grades(
    case: BehaviorCase,
    reason: str,
    conditions: tuple[EvaluationCondition, ...],
) -> dict[str, list[dict[str, Any]]]:
    values = [
        {
            "index": index,
            "check": check,
            "passed": None,
            "confidence": 0,
            "evidence": reason,
        }
        for index, check in enumerate(case.checks)
    ]
    return {condition.id: [dict(value) for value in values] for condition in conditions}


def _safe_call(
    call: Callable[[], dict[str, Any]],
    *,
    case_type: str,
    case_id: str,
    repeat: int,
    condition: EvaluationCondition,
    run_dir: Path,
) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:  # preserve other cases and produce inspectable evidence
        run_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {
            "status": "framework_error",
            "exit_code": None,
            "duration_seconds": 0.0,
            "usage": {},
            "tool_calls": 0,
            "activated": False,
            "final_response": "",
            "case_type": case_type,
            "case_id": case_id,
            "repeat": repeat,
            "condition": condition.id,
            "workspace": "",
            "artifact_delta": {"created": [], "modified": [], "deleted": []},
            "git": {"available": False},
            "error": f"{type(exc).__name__}: {exc}",
        }
        json_dump(run_dir / "run.json", result)
        return result


def _print_plan(
    skill_dir: Path,
    eval_dir: Path,
    trigger_cases: tuple[TriggerCase, ...],
    behavior_cases: tuple[BehaviorCase, ...],
    conditions: tuple[EvaluationCondition, ...],
    args: argparse.Namespace,
) -> None:
    trigger_conditions = tuple(
        condition for condition in conditions if condition.runtime_skill_dir is not None
    )
    trigger_turns = len(trigger_cases) * args.trigger_repeats * len(trigger_conditions)
    behavior_pairs = len(behavior_cases) * args.behavior_repeats
    behavior_turns = behavior_pairs * (len(conditions) + 1)
    condition_labels = " + ".join(condition.display_label.lower() for condition in conditions)
    print(f"Skill: {skill_dir}")
    if len(trigger_conditions) == 1:
        print(
            f"Trigger cases: {len(trigger_cases)} × {args.trigger_repeats} = {trigger_turns} turns"
        )
    else:
        trigger_labels = " + ".join(
            condition.display_label.lower() for condition in trigger_conditions
        )
        print(
            f"Trigger cases: {len(trigger_cases)} × {args.trigger_repeats} × "
            f"({trigger_labels}) = {trigger_turns} turns"
        )
    judge_label = "paired judge" if len(conditions) == 2 else "condition-blind judge"
    print(
        f"Behavior cases (maximum): {len(behavior_cases)} × {args.behavior_repeats} × "
        f"({condition_labels} + {judge_label}) = {behavior_turns} turns"
    )
    print(f"Maximum agent turns: {trigger_turns + behavior_turns}")
    if behavior_cases:
        print("Fixture references:")
        for case in behavior_cases:
            if not case.fixtures:
                print(f"  {case.id}: none")
                continue
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace = Path(temp_dir)
                records, _scripts = materialize_fixtures(
                    eval_dir,
                    case.fixtures,
                    workspace,
                    allow_setup_scripts=args.allow_fixture_scripts,
                )
            details = ", ".join(
                f"{record['reference']} [{record['status']}/{record['mode']}]" for record in records
            )
            print(f"  {case.id}: {details}")


def run_evaluation(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    repo_root = args.repo_root.resolve()
    skill_dir = resolve_skill(repo_root, args.skill)
    candidate_dir = (
        resolve_candidate_skill(repo_root, args.candidate, skill_dir.name)
        if args.candidate is not None
        else None
    )
    if candidate_dir is None:
        return _run_evaluation(args, repo_root, skill_dir, None, None)
    validate_candidate_separation(skill_dir, candidate_dir)

    with tempfile.TemporaryDirectory(prefix="skill-eval-candidate-snapshot-") as temp_dir:
        candidate_runtime_dir = snapshot_candidate_skill(
            candidate_dir,
            Path(temp_dir) / skill_dir.name,
            skill_dir.name,
        )
        return _run_evaluation(
            args,
            repo_root,
            skill_dir,
            candidate_dir,
            candidate_runtime_dir,
        )


def _run_evaluation(
    args: argparse.Namespace,
    repo_root: Path,
    skill_dir: Path,
    candidate_dir: Path | None,
    candidate_runtime_dir: Path | None,
) -> tuple[dict[str, Any], Path]:
    conditions = (
        candidate_evaluation_conditions(skill_dir, candidate_runtime_dir)
        if candidate_runtime_dir is not None
        else default_evaluation_conditions(skill_dir)
    )
    primary_condition = conditions[0]
    candidate_condition = next(
        (condition for condition in conditions if condition.id == "candidate"),
        None,
    )
    spec = load_eval_spec(skill_dir, repo_root / "evals")
    eval_dir = spec.path.parent
    trigger_cases = (
        _select_cases(
            spec.trigger_cases,
            args.trigger_case,
            args.max_trigger_cases,
            kind="trigger",
        )
        if args.suite in {"all", "trigger"}
        else ()
    )
    behavior_cases = (
        _select_cases(
            spec.behavior_cases,
            args.behavior_case,
            args.max_behavior_cases,
            kind="behavior",
        )
        if args.suite in {"all", "behavior"}
        else ()
    )
    if not trigger_cases and not behavior_cases:
        raise EvalError("The selected suite and filters contain no cases")
    if args.plan:
        _print_plan(skill_dir, eval_dir, trigger_cases, behavior_cases, conditions, args)
        return {}, Path()

    runtime_digest = primary_condition.runtime_digest_sha256
    if runtime_digest is None:
        raise EvalError("the primary evaluation condition must include a runtime skill")
    candidate_digest = (
        candidate_condition.runtime_digest_sha256 if candidate_condition is not None else None
    )
    spec_digest = stable_digest(spec.path)
    timestamp = datetime.now(UTC)
    digest_suffix = (
        f"{runtime_digest[:8]}-{candidate_digest[:8]}"
        if candidate_digest is not None
        else runtime_digest[:8]
    )
    run_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{digest_suffix}"
    output_dir = args.output_root.resolve() / spec.skill_name / run_id
    suffix = 1
    while output_dir.exists():
        output_dir = output_dir.with_name(f"{run_id}-{suffix}")
        suffix += 1
    run_id = output_dir.name
    output_dir.mkdir(parents=True)

    runner = CodexRunner(
        conditions=conditions,
        codex_binary=args.codex_binary,
        model=args.model,
        judge_model=args.judge_model,
        timeout_seconds=args.timeout,
        sandbox=args.sandbox,
        peer_skills=(
            tuple(
                path
                for path in discover_repository_skills(repo_root)
                if path not in {skill_dir, candidate_dir}
            )
            if args.skill_universe == "repository"
            else ()
        ),
    )
    print(f"Run {run_id}: {output_dir}", flush=True)

    trigger_conditions = tuple(
        condition for condition in conditions if condition.runtime_skill_dir is not None
    )
    trigger_runs_by_condition: dict[str, list[dict[str, Any]]] = {
        condition.id: [] for condition in trigger_conditions
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        trigger_futures: dict[
            concurrent.futures.Future[dict[str, Any]],
            tuple[str, int, EvaluationCondition],
        ] = {}
        for trigger_case in trigger_cases:
            for repeat in range(1, args.trigger_repeats + 1):
                for condition in trigger_conditions:
                    run_dir = (
                        output_dir
                        / "runs"
                        / "trigger"
                        / trigger_case.id
                        / f"repeat-{repeat}"
                        / condition.id
                    )
                    future = executor.submit(
                        _safe_call,
                        partial(
                            runner.run_task,
                            run_dir=run_dir,
                            workspace_template=None,
                            prompt=trigger_case.query,
                            case_type="trigger",
                            case_id=trigger_case.id,
                            repeat=repeat,
                            condition=condition,
                        ),
                        case_type="trigger",
                        case_id=trigger_case.id,
                        repeat=repeat,
                        condition=condition,
                        run_dir=run_dir,
                    )
                    trigger_futures[future] = (trigger_case.id, repeat, condition)
        for future in concurrent.futures.as_completed(trigger_futures):
            case_id, repeat, condition = trigger_futures[future]
            run = future.result()
            trigger_runs_by_condition[condition.id].append(run)
            print(
                f"trigger {case_id} repeat {repeat} "
                f"{condition.display_label.lower()}: {run['status']} "
                f"activated={run.get('activated')}",
                flush=True,
            )

    behavior_jobs: list[dict[str, Any]] = []
    fixture_warnings: list[str] = []
    for behavior_case in behavior_cases:
        for repeat in range(1, args.behavior_repeats + 1):
            case_root = output_dir / "runs" / "behavior" / behavior_case.id / f"repeat-{repeat}"
            template = case_root / "_fixture-template"
            template.mkdir(parents=True)
            records, setup_scripts = materialize_fixtures(
                eval_dir,
                behavior_case.fixtures,
                template,
                allow_setup_scripts=args.allow_fixture_scripts,
            )
            repository = initialize_fixture_repository(template)
            setup_results = run_fixture_setups(setup_scripts, template, skill_dir)
            fixture_manifest = {
                "records": records,
                "repository": repository,
                "setups": setup_results,
                "initial_snapshot": snapshot_workspace(template),
            }
            fidelity = _fixture_fidelity(records, setup_results, repository)
            fixture_manifest["fidelity"] = fidelity
            json_dump(case_root / "fixture.json", fixture_manifest)
            if fidelity in {"missing", "setup-failed", "degraded", "description-only"}:
                fixture_warnings.append(
                    f"behavior {behavior_case.id} repeat {repeat}: fixture fidelity {fidelity}"
                )
            behavior_jobs.append(
                {
                    "case": behavior_case,
                    "repeat": repeat,
                    "root": case_root,
                    "template": template,
                    "fixture": fixture_manifest,
                    "fidelity": fidelity,
                    "runs": {},
                }
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        behavior_futures: dict[
            concurrent.futures.Future[dict[str, Any]],
            tuple[dict[str, Any], EvaluationCondition],
        ] = {}
        for job in behavior_jobs:
            behavior_case = job["case"]
            repeat = job["repeat"]
            fidelity = job["fidelity"]
            for condition in conditions:
                run_dir = job["root"] / condition.id
                if fidelity in {"missing", "setup-failed"}:
                    job["runs"][condition.id] = _fixture_error_run(
                        case_id=behavior_case.id,
                        repeat=repeat,
                        condition=condition,
                        run_dir=run_dir,
                        fidelity=fidelity,
                    )
                    continue
                future = executor.submit(
                    _safe_call,
                    partial(
                        runner.run_task,
                        run_dir=run_dir,
                        workspace_template=job["template"],
                        prompt=_behavior_prompt(behavior_case),
                        case_type="behavior",
                        case_id=behavior_case.id,
                        repeat=repeat,
                        condition=condition,
                    ),
                    case_type="behavior",
                    case_id=behavior_case.id,
                    repeat=repeat,
                    condition=condition,
                    run_dir=run_dir,
                )
                behavior_futures[future] = (job, condition)
        for future in concurrent.futures.as_completed(behavior_futures):
            job, condition = behavior_futures[future]
            run = future.result()
            job["runs"][condition.id] = run
            print(
                f"behavior {job['case'].id} repeat {job['repeat']} "
                f"{condition.display_label.lower()}: {run['status']}",
                flush=True,
            )

    behavior_results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        judge_futures: dict[concurrent.futures.Future[dict[str, Any]], dict[str, Any]] = {}
        for job in behavior_jobs:
            behavior_case = job["case"]
            runs_by_condition = job["runs"]
            if any(run["status"] == "fixture_error" for run in runs_by_condition.values()):
                behavior_result = {
                    "case_id": behavior_case.id,
                    "repeat": job["repeat"],
                    "prompt": behavior_case.prompt,
                    "expected_behavior": behavior_case.expected_behavior,
                    "checks": list(behavior_case.checks),
                    "fixture_fidelity": job["fidelity"],
                    "fixture": job["fixture"],
                    **{
                        f"{condition.id}_run": runs_by_condition[condition.id]
                        for condition in conditions
                    },
                    "grades": _unknown_grades(
                        behavior_case,
                        "Fixture preparation failed",
                        conditions,
                    ),
                    "judge": {"status": "not-run"},
                }
                behavior_results.append(behavior_result)
                continue
            grade_dir = job["root"] / "judge"
            future = executor.submit(
                runner.grade_pair,
                grade_dir=grade_dir,
                behavior_case=behavior_case,
                repeat=job["repeat"],
                runs_by_condition=runs_by_condition,
            )
            judge_futures[future] = job
        for future in concurrent.futures.as_completed(judge_futures):
            job = judge_futures[future]
            behavior_case = job["case"]
            try:
                judge = future.result()
                grades = (
                    judge["grades"]
                    if judge.get("status") == "completed"
                    else _unknown_grades(
                        behavior_case,
                        "Condition-blind judgment was invalid or incomplete",
                        conditions,
                    )
                )
            except Exception as exc:
                judge = {"status": "framework_error", "error": f"{type(exc).__name__}: {exc}"}
                grades = _unknown_grades(
                    behavior_case,
                    "Condition-blind judge failed",
                    conditions,
                )
            behavior_result = {
                "case_id": behavior_case.id,
                "repeat": job["repeat"],
                "prompt": behavior_case.prompt,
                "expected_behavior": behavior_case.expected_behavior,
                "checks": list(behavior_case.checks),
                "fixture_fidelity": job["fidelity"],
                "fixture": job["fixture"],
                **{f"{condition.id}_run": job["runs"][condition.id] for condition in conditions},
                "grades": grades,
                "judge": judge,
            }
            behavior_results.append(behavior_result)
            print(
                f"judge behavior {behavior_case.id} repeat {job['repeat']}: {judge['status']}",
                flush=True,
            )

    for runs in trigger_runs_by_condition.values():
        runs.sort(key=lambda run: (run["case_id"], run["repeat"]))
    trigger_runs = trigger_runs_by_condition.get(primary_condition.id, [])
    candidate_trigger_runs = (
        trigger_runs_by_condition.get(candidate_condition.id, [])
        if candidate_condition is not None
        else []
    )
    behavior_results.sort(key=lambda item: (item["case_id"], item["repeat"]))
    trigger_summary = (
        summarize_trigger_results(trigger_cases, trigger_runs, threshold=args.activation_threshold)
        if trigger_cases
        else None
    )
    candidate_trigger_summary = (
        summarize_trigger_results(
            trigger_cases,
            candidate_trigger_runs,
            threshold=args.activation_threshold,
        )
        if trigger_cases and candidate_condition is not None
        else None
    )
    behavior_summary = (
        summarize_behavior_results(behavior_results, conditions) if behavior_results else None
    )
    profile = efficacy_profile(trigger_summary, behavior_summary, conditions)

    warnings = list(dict.fromkeys(fixture_warnings))
    if trigger_cases and args.trigger_repeats < 2:
        warnings.append("Trigger cases ran once; activation reliability is not measured")
    if behavior_cases and args.behavior_repeats < 2:
        warnings.append("Behavior cases ran once; stochastic variance is not measured")
    if any(result.get("judge", {}).get("status") != "completed" for result in behavior_results):
        warnings.append(
            "One or more "
            + ("paired" if len(conditions) == 2 else "condition-blind")
            + " judgments were unavailable or invalid"
        )
    if args.sandbox == "danger-full-access":
        warnings.append("Behavior runs used danger-full-access sandboxing")

    reproduce = [
        "python3",
        "scripts/eval_skills.py",
        "--skill",
        args.skill,
        "--suite",
        args.suite,
        "--trigger-repeats",
        str(args.trigger_repeats),
        "--behavior-repeats",
        str(args.behavior_repeats),
        "--activation-threshold",
        str(args.activation_threshold),
        "--jobs",
        str(args.jobs),
        "--timeout",
        str(args.timeout),
        "--codex-binary",
        args.codex_binary,
        "--skill-universe",
        args.skill_universe,
        "--sandbox",
        args.sandbox,
        "--allow-fixture-scripts" if args.allow_fixture_scripts else "--no-allow-fixture-scripts",
        "--output-root",
        str(args.output_root),
    ]
    if args.repo_root.resolve() != REPO_ROOT.resolve():
        reproduce.extend(["--repo-root", str(args.repo_root)])
    if args.candidate is not None:
        reproduce.extend(["--candidate", str(args.candidate)])
    if args.max_trigger_cases is not None:
        reproduce.extend(["--max-trigger-cases", str(args.max_trigger_cases)])
    if args.max_behavior_cases is not None:
        reproduce.extend(["--max-behavior-cases", str(args.max_behavior_cases)])
    for case_id in args.trigger_case:
        reproduce.extend(["--trigger-case", case_id])
    for case_id in args.behavior_case:
        reproduce.extend(["--behavior-case", case_id])
    if args.model:
        reproduce.extend(["--model", args.model])
    if args.judge_model:
        reproduce.extend(["--judge-model", args.judge_model])
    if args.fail_under is not None:
        reproduce.extend(["--fail-under", str(args.fail_under)])

    result: dict[str, Any] = {
        "schema_version": 2 if candidate_condition is not None else 1,
        "run_id": run_id,
        "generated_at": timestamp.isoformat(),
        "repository": {"root": str(repo_root), **_git_metadata(repo_root)},
        "skill": {
            "name": spec.skill_name,
            "path": str(skill_dir),
            "eval_path": str(eval_dir),
            "runtime_digest_sha256": runtime_digest,
            "eval_spec_digest_sha256": spec_digest,
        },
        "runtime": {
            "adapter": "codex",
            "codex_version": runner.version,
            "model": args.model or "runtime-default",
            "judge_model": args.judge_model or args.model or "runtime-default",
            "sandbox": args.sandbox,
            "timeout_seconds": args.timeout,
            "jobs": args.jobs,
            "skill_universe": args.skill_universe,
            "peer_skills": [path.name for path in runner.peer_skills],
        },
        "config": {
            "suite": args.suite,
            "trigger_repeats": args.trigger_repeats,
            "behavior_repeats": args.behavior_repeats,
            "activation_threshold": args.activation_threshold,
            "allow_fixture_scripts": args.allow_fixture_scripts,
            "skill_universe": args.skill_universe,
        },
        "integrity": {
            "evals_withheld": True,
            "fresh_contexts": True,
            "blind_paired_grading": True,
            "peer_skill_parity": args.skill_universe == "repository",
            "warnings": warnings,
        },
        "trigger": {"runs": trigger_runs, "summary": trigger_summary}
        if trigger_summary is not None
        else None,
        "behavior": {"results": behavior_results, "summary": behavior_summary}
        if behavior_summary is not None
        else None,
        "efficacy": profile,
        "reproduce_command": shlex.join(reproduce),
    }
    if candidate_condition is not None and candidate_dir is not None:
        result["candidate"] = {
            "name": spec.skill_name,
            "path": str(candidate_dir),
            "runtime_digest_sha256": candidate_digest,
        }
        result["candidate_trigger"] = (
            {"runs": candidate_trigger_runs, "summary": candidate_trigger_summary}
            if candidate_trigger_summary is not None
            else None
        )
        result["config"]["candidate"] = str(args.candidate)
        result["integrity"]["blind_condition_grading"] = True
    json_dump(output_dir / "results.json", result)
    markdown, html = write_reports(output_dir, result, conditions)
    print(f"Report: {markdown}", flush=True)
    print(f"Visual report: {html}", flush=True)
    print(
        f"Verdict: {profile['verdict']} · absolute efficacy "
        f"{profile['absolute_efficacy_percent']:.1f}%"
        if profile["absolute_efficacy_percent"] is not None
        else f"Verdict: {profile['verdict']} · absolute efficacy unavailable",
        flush=True,
    )
    return result, output_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _positive_int(args.trigger_repeats, "--trigger-repeats")
        _positive_int(args.behavior_repeats, "--behavior-repeats")
        _positive_int(args.jobs, "--jobs")
        _positive_int(args.timeout, "--timeout")
        _positive_int(args.max_trigger_cases, "--max-trigger-cases")
        _positive_int(args.max_behavior_cases, "--max-behavior-cases")
        if not 0 <= args.activation_threshold <= 1:
            raise EvalError("--activation-threshold must be between 0 and 1")
        if args.fail_under is not None and not 0 <= args.fail_under <= 100:
            raise EvalError("--fail-under must be between 0 and 100")
        result, _output = run_evaluation(args)
    except EvalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.plan:
        return 0
    if args.fail_under is not None:
        score = result["efficacy"]["absolute_efficacy_percent"]
        if score is None or score < args.fail_under:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
