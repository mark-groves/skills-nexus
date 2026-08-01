#!/usr/bin/env python3
"""Run candidate capability reviews across pinned task and judge harness profiles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_eval.core import (
    EvalError,
    discover_repository_skills,
    load_eval_spec,
    resolve_candidate_skill,
    resolve_skill,
    validate_candidate_separation,
)
from skill_review.core import (
    DISPOSITIONS,
    CapabilityReviewConfig,
    EvaluationRunner,
    RoutineScreenConfig,
    build_durable_summary,
    export_durable_summary,
    load_case_groups,
    load_profile_contract,
    load_routine_screen_contract,
    run_capability_review,
    run_routine_screen,
    select_profiles,
    validate_durable_disposition,
    validate_routine_escalation,
    validate_universes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    """Build the capability-review command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded routine screen or full candidate evaluation matrix "
            "across pinned multi-harness model profiles."
        )
    )
    parser.add_argument(
        "--workflow",
        choices=("full", "routine"),
        default="full",
        help="Run the compatibility-preserving full matrix or the bounded routine screen",
    )
    parser.add_argument("--skill", required=True, help="Short name, full skill id, or directory")
    parser.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Publishable candidate skill directory",
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=REPO_ROOT / "eval-profiles.json",
        help="Versioned model-profile contract",
    )
    parser.add_argument(
        "--observed-profile",
        action="append",
        default=[],
        metavar="ID",
        help="Observed profile to include; required profiles always run",
    )
    parser.add_argument(
        "--include-all-observed",
        action="store_true",
        help="Run every observed profile in the contract",
    )
    parser.add_argument(
        "--case-groups",
        type=Path,
        help=(
            "Versioned complete case partition identifying development and held-back groups; "
            "without it all cases are labeled development and evidence remains insufficient"
        ),
    )
    parser.add_argument(
        "--universe",
        action="append",
        choices=("repository", "isolated"),
        default=[],
        help="Skill universe to run; omit to run both",
    )
    parser.add_argument(
        "--universe-limitation",
        help="Required documented scope limitation when selecting only one universe",
    )
    parser.add_argument("--trigger-repeats", type=int)
    parser.add_argument("--behavior-repeats", type=int)
    parser.add_argument("--activation-threshold", type=float, default=0.5)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--routine-contract",
        type=Path,
        help="Repository-owned high-signal routine selection; defaults beside evals.json",
    )
    parser.add_argument(
        "--budget-seconds",
        type=int,
        help="Routine wall-clock budget; may not exceed one hour",
    )
    parser.add_argument(
        "--deadline-seconds",
        type=int,
        help="Routine evaluator hard stop, leaving five minutes for aggregation",
    )
    parser.add_argument(
        "--escalate-from",
        type=Path,
        help="Eligible local routine review.json pinned to this full matrix",
    )
    parser.add_argument(
        "--human-opt-in",
        action="store_true",
        help="Confirm the human decision to run a full escalation",
    )
    parser.add_argument("--codex-binary", default="codex")
    parser.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
    )
    parser.add_argument(
        "--allow-fixture-scripts",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".skill-evals",
        help="Ignored local root retaining complete review runs",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument(
        "--expected-current-digest",
        help="Reject a Current runtime package that differs from this SHA-256",
    )
    parser.add_argument(
        "--expected-candidate-digest",
        help="Reject a Candidate runtime package that differs from this SHA-256",
    )
    parser.add_argument(
        "--expected-eval-digest",
        help="Reject an eval bundle, including fixtures, that differs from this SHA-256",
    )
    parser.add_argument(
        "--expected-profiles-digest",
        help="Reject a normalized profile contract that differs from this SHA-256",
    )
    parser.add_argument(
        "--expected-case-groups-digest",
        help="Reject normalized case groups that differ from this SHA-256",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Opt in to bounded deterministic JSON and Markdown durable summaries",
    )
    parser.add_argument("--reviewer", help="Human reviewer identity for durable export")
    parser.add_argument(
        "--disposition",
        choices=sorted(DISPOSITIONS),
        help="Human-reviewed bounded disposition for durable export",
    )
    parser.add_argument(
        "--disposition-rationale",
        help="Human reviewer rationale for the durable disposition",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Validate inputs and show the profile/universe matrix without running models",
    )
    return parser


def _configuration(
    args: argparse.Namespace,
) -> tuple[CapabilityReviewConfig, RoutineScreenConfig | None]:
    """Load and validate all review contracts before any model call."""
    repo_root = args.repo_root.resolve()
    contract = load_profile_contract(args.profiles)
    profiles = select_profiles(
        contract,
        args.observed_profile,
        include_all_observed=args.include_all_observed,
    )
    universes = validate_universes(args.universe, args.universe_limitation)
    skill_dir = resolve_skill(repo_root, args.skill)
    candidate_dir = resolve_candidate_skill(repo_root, args.candidate, skill_dir.name)
    validate_candidate_separation(skill_dir, candidate_dir)
    for peer_dir in discover_repository_skills(repo_root):
        if peer_dir not in {skill_dir, candidate_dir}:
            validate_candidate_separation(peer_dir, candidate_dir)
    spec = load_eval_spec(skill_dir, repo_root / "evals")
    case_group_source = args.case_groups
    if args.workflow == "routine" and case_group_source is None:
        case_group_source = spec.path.parent / "capability-case-groups.json"
    groups = load_case_groups(case_group_source, spec)
    trigger_repeats = args.trigger_repeats
    behavior_repeats = args.behavior_repeats
    if trigger_repeats is None:
        trigger_repeats = 1 if args.workflow == "routine" else 2
    if behavior_repeats is None:
        behavior_repeats = 1 if args.workflow == "routine" else 2
    config = CapabilityReviewConfig(
        repo_root=repo_root,
        skill=args.skill,
        candidate=args.candidate,
        profile_source=args.profiles,
        contract=contract,
        profiles=profiles,
        case_group_source=case_group_source,
        case_groups=groups,
        universes=universes,
        universe_limitation=args.universe_limitation,
        trigger_repeats=trigger_repeats,
        behavior_repeats=behavior_repeats,
        activation_threshold=args.activation_threshold,
        jobs=args.jobs,
        timeout=args.timeout,
        codex_binary=args.codex_binary,
        sandbox=args.sandbox,
        allow_fixture_scripts=args.allow_fixture_scripts,
        output_root=args.output_root,
        expected_current_digest=args.expected_current_digest,
        expected_candidate_digest=args.expected_candidate_digest,
        expected_eval_digest=args.expected_eval_digest,
        expected_profiles_digest=args.expected_profiles_digest,
        expected_case_groups_digest=args.expected_case_groups_digest,
    )
    if args.workflow == "full":
        return config, None
    routine_source = args.routine_contract or spec.path.parent / "routine-screen.json"
    routine = RoutineScreenConfig(
        review=config,
        contract_source=routine_source,
        contract=load_routine_screen_contract(routine_source, spec, groups),
        budget_seconds=args.budget_seconds if args.budget_seconds is not None else 3600,
        deadline_seconds=args.deadline_seconds if args.deadline_seconds is not None else 3300,
    )
    return config, routine


def _validate_export_args(args: argparse.Namespace) -> None:
    """Require a complete human disposition only for explicit export."""
    supplied = any((args.reviewer, args.disposition, args.disposition_rationale))
    if args.export and not all((args.reviewer, args.disposition, args.disposition_rationale)):
        raise EvalError("--export requires --reviewer, --disposition, and --disposition-rationale")
    if args.export:
        validate_durable_disposition(
            disposition=args.disposition,
            reviewer=args.reviewer,
            rationale=args.disposition_rationale,
        )
    if not args.export and supplied:
        raise EvalError("--reviewer, --disposition, and --disposition-rationale require --export")
    if args.plan and args.export:
        raise EvalError("--plan cannot export a durable review")
    if args.workflow == "routine" and args.export:
        raise EvalError("Routine screens are local report-only evidence and cannot be exported")
    if args.workflow == "routine" and (args.observed_profile or args.include_all_observed):
        raise EvalError("Routine screens run required profiles only")
    if args.workflow == "routine" and (args.escalate_from or args.human_opt_in):
        raise EvalError("Routine screens cannot use full-escalation controls")
    if args.workflow == "full" and (
        args.routine_contract is not None
        or args.budget_seconds is not None
        or args.deadline_seconds is not None
    ):
        raise EvalError(
            "--routine-contract, --budget-seconds, and --deadline-seconds "
            "require --workflow routine"
        )
    if args.escalate_from is not None and not args.human_opt_in:
        raise EvalError("--escalate-from requires --human-opt-in")
    if args.human_opt_in and args.escalate_from is None:
        raise EvalError("--human-opt-in requires --escalate-from")


def main(
    argv: list[str] | None = None,
    *,
    evaluation_runner: EvaluationRunner | None = None,
) -> int:
    """Run, plan, or export a capability review."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_export_args(args)
        config, routine = _configuration(args)
        if args.escalate_from is not None:
            validate_routine_escalation(args.escalate_from, config)
        if args.plan:
            if routine is not None:
                discovery = (
                    "compact blocking positive/near-miss set when discovery inputs change; "
                    "otherwise omitted as observational"
                )
                print("Workflow: routine (report only)")
                print("Behavior cases: " + ", ".join(routine.contract.behavior_cases))
                print("Trigger policy: " + discovery)
                print(f"Budget: {routine.budget_seconds}s; hard stop: {routine.deadline_seconds}s")
            print(
                "Judge policy: "
                f"{config.contract.judge_policy.adapter}/"
                f"{config.contract.judge_policy.model}"
            )
            print(
                "Profiles: "
                + ", ".join(
                    f"{item.id} ({item.role}, {item.adapter}/{item.model})"
                    for item in config.profiles
                )
            )
            print("Universes: " + ", ".join(config.universes))
            print(
                "Case groups: "
                + ", ".join(f"{item.id} ({item.kind})" for item in config.case_groups)
            )
            print(f"Matrix cells: {len(config.profiles) * len(config.universes)}")
            return 0
        if evaluation_runner is None:
            from eval_skills import run_evaluation

            evaluation_runner = run_evaluation
        if routine is not None:
            review, local_root = run_routine_screen(routine, evaluation_runner)
            print(f"Local routine screen: {local_root}")
            print(f"Routine outcome: {review['aggregate']['outcome']}")
            return 0 if review["aggregate"]["outcome"] == "eligible-for-escalation" else 2
        review, local_root = run_capability_review(config, evaluation_runner)
        print(f"Local capability review: {local_root}")
        print(f"Evidence verdict: {review['aggregate']['verdict']}")
        if args.export:
            summary = build_durable_summary(
                review,
                config,
                disposition=args.disposition,
                reviewer=args.reviewer,
                rationale=args.disposition_rationale,
            )
            json_path, markdown_path = export_durable_summary(
                summary,
                repo_root=config.repo_root,
            )
            print(f"Durable JSON: {json_path}")
            print(f"Durable Markdown: {markdown_path}")
    except EvalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0 if review["aggregate"]["verdict"] == "approved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
