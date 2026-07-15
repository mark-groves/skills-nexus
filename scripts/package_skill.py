#!/usr/bin/env python3
"""Create a clean runtime copy of one canonical skill."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from skill_eval.core import EvalError, runtime_skill_copy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Canonical skill directory")
    parser.add_argument("destination", type=Path, help="Runtime package destination")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source.is_symlink():
        print(f"error: source skill directory may not be a symlink: {args.source}", file=sys.stderr)
        return 1
    source = args.source.resolve()
    destination = args.destination.absolute()
    resolved_destination = destination.resolve()
    if not (source / "SKILL.md").is_file():
        print(f"error: source is not a skill directory: {source}", file=sys.stderr)
        return 1

    if (
        resolved_destination == source
        or source in resolved_destination.parents
        or resolved_destination in source.parents
    ):
        print("error: source and destination skill trees may not overlap", file=sys.stderr)
        return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.name}-package-", dir=destination.parent
        ) as temp_dir:
            staged = Path(temp_dir) / destination.name
            runtime_skill_copy(source, staged)
            if destination.is_symlink() or destination.is_file():
                destination.unlink()
            elif destination.is_dir():
                shutil.rmtree(destination)
            staged.rename(destination)
    except EvalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
