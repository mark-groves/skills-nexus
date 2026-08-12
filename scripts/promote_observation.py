#!/usr/bin/env python3
"""Promote a classified observation into evals.json without editing the skill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_observation import ObservationError, load_stored_observation
from skill_triage import (
    UNPROMOTABLE_CLASSIFICATIONS,
    close_disposition,
    promote_into_eval_suite,
    redact_observation,
    require_open_disposition,
    write_disposition,
    write_redacted_observation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Stored observation JSON")
    parser.add_argument("--reason", required=True, help="Why this observation becomes a regression")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".skill-feedback" / "triage",
        help="Private triage directory",
    )
    parser.add_argument(
        "--evals-root",
        type=Path,
        default=REPO_ROOT / "evals",
        help="Repository evals directory",
    )
    parser.add_argument(
        "--group",
        default="development",
        help="Case group that receives new case ids when groups exist",
    )
    parser.add_argument("--trigger-query", help="Trigger eval query to append")
    parser.add_argument(
        "--should-trigger",
        choices=("true", "false"),
        help="Whether the trigger query should activate the skill",
    )
    parser.add_argument("--behavior-prompt", help="Behavior eval prompt to append")
    parser.add_argument("--expected-behavior", help="Expected behavior for the new case")
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        help="Behavior check string; repeat for multiple checks",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="Behavior fixture name; repeat for multiple fixtures",
    )
    return parser


def _trigger_case(args: argparse.Namespace) -> dict[str, object] | None:
    if args.trigger_query is None:
        if args.should_trigger is not None:
            raise ObservationError("--should-trigger requires --trigger-query")
        return None
    if args.should_trigger is None:
        raise ObservationError("--trigger-query requires --should-trigger")
    query = args.trigger_query.strip()
    if not query:
        raise ObservationError("--trigger-query must be a non-empty string")
    return {"query": query, "should_trigger": args.should_trigger == "true"}


def _behavior_case(args: argparse.Namespace) -> dict[str, object] | None:
    if args.behavior_prompt is None:
        extra = bool(args.expected_behavior or args.check or args.fixture)
        if extra:
            raise ObservationError(
                "--expected-behavior, --check, and --fixture require --behavior-prompt"
            )
        return None
    prompt = args.behavior_prompt.strip()
    expected = (args.expected_behavior or "").strip()
    checks = [item.strip() for item in args.check if item.strip()]
    fixtures = [item.strip() for item in args.fixture if item.strip()]
    if not prompt:
        raise ObservationError("--behavior-prompt must be a non-empty string")
    if not expected:
        raise ObservationError("--behavior-prompt requires --expected-behavior")
    if not checks:
        raise ObservationError("--behavior-prompt requires at least one --check")
    return {
        "prompt": prompt,
        "expected_behavior": expected,
        "fixtures": fixtures,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        trigger = _trigger_case(args)
        behavior = _behavior_case(args)
        if trigger is None and behavior is None:
            raise ObservationError("promotion requires --trigger-query and/or --behavior-prompt")
        observation = load_stored_observation(args.input)
        existing = require_open_disposition(
            args.output_root,
            observation["skill"]["id"],
            observation["observation_id"],
        )
        if existing["classification"] in UNPROMOTABLE_CLASSIFICATIONS:
            raise ObservationError(
                f"classification {existing['classification']} cannot be promoted into evals.json"
            )
        redacted, _counts = redact_observation(observation)
        write_redacted_observation(redacted, args.output_root)
        eval_path, trigger_ids, behavior_ids, _groups_path = promote_into_eval_suite(
            skill_id=observation["skill"]["id"],
            evals_root=args.evals_root,
            trigger=trigger,
            behavior=behavior,
            group_id=args.group,
        )
        destination = write_disposition(
            close_disposition(existing, disposition="accept", reason=args.reason),
            args.output_root,
        )
    except (ObservationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(destination)
    print(eval_path, file=sys.stderr)
    if trigger_ids:
        print("trigger " + ", ".join(trigger_ids), file=sys.stderr)
    if behavior_ids:
        print("behavior " + ", ".join(behavior_ids), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
