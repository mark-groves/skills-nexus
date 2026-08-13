#!/usr/bin/env python3
"""Redact a stored observation and write an open triage disposition."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_observation import ObservationError, load_stored_observation
from skill_triage import (
    CLASSIFICATIONS,
    build_disposition,
    redact_observation,
    refuse_closed_disposition,
    write_disposition,
    write_redacted_observation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Stored observation JSON")
    parser.add_argument(
        "--class",
        dest="classification",
        required=True,
        choices=sorted(CLASSIFICATIONS),
        help="Change surface for this observation",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".skill-feedback" / "triage",
        help="Private triage directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        observation = load_stored_observation(args.input)
        refuse_closed_disposition(
            args.output_root,
            observation["skill"]["id"],
            observation["observation_id"],
        )
        redacted, _counts = redact_observation(observation)
        write_redacted_observation(redacted, args.output_root)
        record = build_disposition(redacted, classification=args.classification)
        destination = write_disposition(record, args.output_root)
    except (ObservationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
