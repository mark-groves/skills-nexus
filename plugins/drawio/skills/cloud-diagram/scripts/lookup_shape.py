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

from gcp_card import emit_gcp_service_card  # noqa: E402
from shape_catalog import PROVIDER_FILES, load_common_shapes, resolve_shape  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDER_FILES))
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--card",
        action="store_true",
        help="Emit paste-ready GCP Service Card XML (required for GCP product icons)",
    )
    parser.add_argument("--x", type=float, default=200.0, help="Card x when using --card")
    parser.add_argument("--y", type=float, default=150.0, help="Card y when using --card")
    parser.add_argument("--cell-id", default=None, help="Card cell id when using --card")
    parser.add_argument(
        "--label",
        default=None,
        help="Primary card label (defaults to catalog title) when using --card",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Secondary card label line when using --card",
    )
    parser.add_argument("query", nargs="?")
    args = parser.parse_args(argv)

    common = load_common_shapes()
    if args.list:
        services = common["providers"][args.provider]["services"]
        print("\n".join(sorted(services)))
        return 0

    if args.query is None:
        parser.error("query is required unless --list is used")

    if args.card and args.provider != "gcp":
        parser.error("--card is only supported for --provider gcp")

    shape = resolve_shape(args.provider, args.query, common)
    if shape is None:
        print(
            f"MISS: {args.provider!r} {args.query!r}. "
            "Confirmed miss only → labeled generic rounded rectangle.",
            file=sys.stderr,
        )
        return 2

    if args.card:
        try:
            print(
                emit_gcp_service_card(
                    shape,
                    x=args.x,
                    y=args.y,
                    cell_id=args.cell_id,
                    name=args.label,
                    category=args.category,
                )
            )
        except ValueError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 2
        return 0

    if args.as_json:
        print(json.dumps(shape, indent=2))
        return 0

    print(f"id: {shape.get('id')}")
    print(f"title: {shape['title']}")
    print(f"kind: {shape['kind']}")
    print(f"size: {shape['size']}")
    print(f"tokens: {', '.join(shape.get('tokens') or [])}")
    print(f"style: {shape['style']}")
    if shape.get("kind") == "gcp_card_icon":
        print(
            "note: GCP product icons must be Service Cards. "
            "Re-run with --card for paste-ready XML; do not paste style as a "
            "standalone icon.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
