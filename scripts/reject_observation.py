#!/usr/bin/env python3
"""Close a classified observation as reject or insufficient without editing skills or evals."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from skill_observation import ObservationError, load_stored_observation
from skill_triage import (
    close_disposition,
    redact_observation,
    require_open_disposition,
    write_disposition,
    write_redacted_observation,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_CLOSE_DISPOSITIONS = ("reject", "insufficient")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Stored observation JSON")
    parser.add_argument(
        "--disposition",
        choices=_CLOSE_DISPOSITIONS,
        default="reject",
        help="Terminal triage decision",
    )
    parser.add_argument("--reason", required=True, help="Why the observation is not promoted")
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
        existing = require_open_disposition(
            args.output_root,
            observation["skill"]["id"],
            observation["observation_id"],
        )
        redacted, _counts = redact_observation(observation)
        write_redacted_observation(redacted, args.output_root)
        destination = write_disposition(
            close_disposition(existing, disposition=args.disposition, reason=args.reason),
            args.output_root,
        )
    except (ObservationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
