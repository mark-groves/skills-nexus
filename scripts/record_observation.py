#!/usr/bin/env python3
"""Validate and record an untrusted skill-execution observation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_eval.core import EvalError, discover_repository_skills, resolve_skill
from skill_observation import ObservationError, build_observation, load_draft, write_observation

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="Canonical skill name or directory")
    parser.add_argument("--input", required=True, type=Path, help="JSON observation draft")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".skill-feedback" / "inbox",
        help="Private observation inbox",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    try:
        skill_dir = resolve_skill(repo_root, args.skill)
        if skill_dir not in set(discover_repository_skills(repo_root)):
            raise ObservationError(
                f"observation skill must be canonical under {repo_root / 'skills'}: {skill_dir}"
            )
        draft = load_draft(args.input)
        observation = build_observation(draft, skill_dir=skill_dir, repo_root=repo_root)
        destination = write_observation(observation, args.output_root)
    except (EvalError, ObservationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
