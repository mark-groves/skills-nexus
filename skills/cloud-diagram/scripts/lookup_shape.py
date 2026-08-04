#!/usr/bin/env python3
"""Resolve a cloud service name to a verified draw.io style string."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from shape_catalog import PROVIDER_FILES, load_common_shapes, resolve_shape  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDER_FILES))
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("query", nargs="?")
    args = parser.parse_args(argv)

    common = load_common_shapes()
    if args.list:
        services = common["providers"][args.provider]["services"]
        print("\n".join(sorted(services)))
        return 0

    if args.query is None:
        parser.error("query is required unless --list is used")

    shape = resolve_shape(args.provider, args.query, common)
    if shape is None:
        print(
            f"MISS: {args.provider!r} {args.query!r}. "
            "Confirmed miss only → labeled generic rounded rectangle.",
            file=sys.stderr,
        )
        return 2

    if args.as_json:
        print(json.dumps(shape, indent=2))
        return 0

    print(f"id: {shape.get('id')}")
    print(f"title: {shape['title']}")
    print(f"kind: {shape['kind']}")
    print(f"size: {shape['size']}")
    print(f"tokens: {', '.join(shape.get('tokens') or [])}")
    print(f"style: {shape['style']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
