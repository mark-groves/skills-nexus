#!/usr/bin/env python3
"""Run candidate capability reviews across pinned Codex model profiles."""

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
    build_durable_summary,
    export_durable_summary,
    load_case_groups,
    load_profile_contract,
    run_capability_review,
    select_profiles,
    validate_durable_disposition,
    validate_universes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    """Build the capability-review command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Run one full candidate evaluation suite across required and selected "
            "observed Codex model profiles."
        )
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
    parser.add_argument("--trigger-repeats", type=int, default=2)
    parser.add_argument("--behavior-repeats", type=int, default=2)
    parser.add_argument("--activation-threshold", type=float, default=0.5)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
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


def _configuration(args: argparse.Namespace) -> CapabilityReviewConfig:
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
    groups = load_case_groups(args.case_groups, spec)
    return CapabilityReviewConfig(
        repo_root=repo_root,
        skill=args.skill,
        candidate=args.candidate,
        profile_source=args.profiles,
        contract=contract,
        profiles=profiles,
        case_group_source=args.case_groups,
        case_groups=groups,
        universes=universes,
        universe_limitation=args.universe_limitation,
        trigger_repeats=args.trigger_repeats,
        behavior_repeats=args.behavior_repeats,
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
        config = _configuration(args)
        if args.plan:
            print("Profiles: " + ", ".join(f"{item.id} ({item.role})" for item in config.profiles))
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
