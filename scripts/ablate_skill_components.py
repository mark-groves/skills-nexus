#!/usr/bin/env python3
"""Evaluate repository-owned skill components with greedy backward elimination."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_eval.core import EvalError, load_eval_spec, resolve_skill
from skill_review.ablation import (
    CapabilityRunner,
    ComponentAblationConfig,
    ComponentContract,
    load_component_contract,
    run_component_ablation,
    validate_component_metadata_source,
)
from skill_review.core import (
    CapabilityReviewConfig,
    EvaluationRunner,
    load_case_groups,
    load_profile_contract,
    run_capability_review,
    select_profiles,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    """Build the component-ablation command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            "Greedily remove exact unprotected skill sections using the complete "
            "capability-review matrix, then rerun the combined candidate."
        )
    )
    parser.add_argument("--skill", required=True, help="Short name, full skill id, or directory")
    parser.add_argument(
        "--components",
        type=Path,
        help="Versioned component metadata; defaults to evals/<skill>/components.json",
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        help="Versioned model-profile contract; defaults under --repo-root",
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
        help="Versioned complete development and held-back case partition",
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
        help="Ignored local root; defaults to .skill-evals under --repo-root",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Validate selectors and show protected components without running models",
    )
    return parser


def _configuration(
    args: argparse.Namespace,
) -> tuple[ComponentAblationConfig, ComponentContract]:
    """Load every repository-owned contract before a model call."""
    repo_root = args.repo_root.resolve()
    skill_dir = resolve_skill(repo_root, args.skill)
    components_source = (
        args.components
        if args.components is not None
        else repo_root / "evals" / skill_dir.name / "components.json"
    )
    validate_component_metadata_source(repo_root, skill_dir, components_source)
    contract = load_component_contract(components_source, skill_dir)
    profile_source = (
        args.profiles if args.profiles is not None else repo_root / "eval-profiles.json"
    )
    output_root = args.output_root if args.output_root is not None else repo_root / ".skill-evals"
    profile_contract = load_profile_contract(profile_source)
    profiles = select_profiles(
        profile_contract,
        args.observed_profile,
        include_all_observed=args.include_all_observed,
    )
    spec = load_eval_spec(skill_dir, repo_root / "evals")
    groups = load_case_groups(args.case_groups, spec)
    review = CapabilityReviewConfig(
        repo_root=repo_root,
        skill=args.skill,
        candidate=output_root / "pending-component-candidate",
        profile_source=profile_source,
        contract=profile_contract,
        profiles=profiles,
        case_group_source=args.case_groups,
        case_groups=groups,
        universes=("repository", "isolated"),
        universe_limitation=None,
        trigger_repeats=args.trigger_repeats,
        behavior_repeats=args.behavior_repeats,
        activation_threshold=args.activation_threshold,
        jobs=args.jobs,
        timeout=args.timeout,
        codex_binary=args.codex_binary,
        sandbox=args.sandbox,
        allow_fixture_scripts=args.allow_fixture_scripts,
        output_root=output_root,
    )
    return (
        ComponentAblationConfig(
            review=review,
            components_source=components_source,
            output_root=output_root,
        ),
        contract,
    )


def main(
    argv: list[str] | None = None,
    *,
    evaluation_runner: EvaluationRunner | None = None,
    capability_runner: CapabilityRunner | None = None,
) -> int:
    """Plan or execute one component-ablation review."""
    args = build_parser().parse_args(argv)
    try:
        config, contract = _configuration(args)
        if args.plan:
            print(f"Components: {len(contract.components)}")
            for component in contract.components:
                status = "protected" if component.protected else "eligible"
                print(f"- {component.id}: {status} ({component.source} {component.heading})")
            print(
                "Profiles: "
                + ", ".join(f"{profile.id} ({profile.role})" for profile in config.review.profiles)
            )
            print("Universes: repository, isolated")
            return 0
        if capability_runner is None:
            if evaluation_runner is None:
                from eval_skills import run_evaluation

                evaluation_runner = run_evaluation

            def capability_runner(review_config: CapabilityReviewConfig) -> tuple[dict, Path]:
                assert evaluation_runner is not None
                return run_capability_review(review_config, evaluation_runner)

        record, local_root = run_component_ablation(config, capability_runner)
        print(f"Local component decision: {local_root / 'decision.json'}")
        print(f"Outcome: {record['outcome']}")
        final = record["final_verification"]
        if isinstance(final, dict):
            print(f"Final evidence verdict: {final['verdict']}")
        return 0 if record["outcome"] == "propose-reduction" else 2
    except EvalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
