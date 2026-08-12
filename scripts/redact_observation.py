#!/usr/bin/env python3
"""Validate a stored observation, redact secrets and PII, and write a private copy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_observation import ObservationError, load_stored_observation
from skill_triage import redact_observation, write_redacted_observation

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Stored observation JSON")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".skill-feedback" / "triage",
        help="Private redacted triage directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        observation = load_stored_observation(args.input)
        redacted, _counts = redact_observation(observation)
        destination = write_redacted_observation(redacted, args.output_root)
    except (ObservationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
