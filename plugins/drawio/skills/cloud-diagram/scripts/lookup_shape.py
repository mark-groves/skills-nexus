#!/usr/bin/env python3
"""Resolve a cloud service name to a verified draw.io style string."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from gcp_card import emit_gcp_service_card  # noqa: E402
from safe_names import (  # noqa: E402
    LookupRequest,
    UnsafeValueError,
    load_json_object,
    parse_lookup_payload,
    require_finite_number,
    require_name,
)
from shape_catalog import PROVIDER_FILES, load_common_shapes, resolve_shape  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(PROVIDER_FILES))
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--card",
        action="store_true",
        help="Emit paste-ready GCP Service Card XML (required for GCP product icons)",
    )
    parser.add_argument("--x", type=float, default=None, help="Card x when using --card")
    parser.add_argument("--y", type=float, default=None, help="Card y when using --card")
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
    parser.add_argument(
        "--input-file",
        help=(
            "JSON file (or - for stdin) of provider, query, label, and category. "
            "Untrusted names belong here, not in the shell command."
        ),
    )
    parser.add_argument("query", nargs="?")
    return parser


def _coordinate(value: float | None, default: float, field: str) -> float:
    if value is None:
        return default
    return require_finite_number(value, field)


def _requests_from_args(args: argparse.Namespace) -> list[LookupRequest]:
    if args.input_file:
        if any(
            (
                args.provider is not None,
                args.query is not None,
                args.as_json,
                args.list,
                args.card,
                args.x is not None,
                args.y is not None,
                args.cell_id is not None,
                args.label is not None,
                args.category is not None,
            )
        ):
            raise UnsafeValueError("--input-file cannot be combined with other lookup arguments")
        return parse_lookup_payload(load_json_object(args.input_file), frozenset(PROVIDER_FILES))

    if args.provider is None:
        raise UnsafeValueError("--provider is required")
    if args.card and args.provider != "gcp":
        raise UnsafeValueError("--card is only supported for --provider gcp")
    label = require_name(args.label, "label") if args.label is not None else None
    category = require_name(args.category, "category") if args.category is not None else None
    cell_id = require_name(args.cell_id, "cell_id") if args.cell_id is not None else None
    query = require_name(args.query, "query") if args.query is not None else None
    if not args.list and query is None:
        raise UnsafeValueError("query is required unless --list is used")
    return [
        LookupRequest(
            provider=args.provider,
            query=query,
            list_services=args.list,
            card=args.card,
            x=_coordinate(args.x, 200.0, "x"),
            y=_coordinate(args.y, 150.0, "y"),
            label=label,
            category=category,
            cell_id=cell_id,
            as_json=args.as_json,
        )
    ]


def _text_shape(shape: dict[str, Any]) -> str:
    lines = [
        f"id: {shape.get('id')}",
        f"title: {shape['title']}",
        f"kind: {shape['kind']}",
        f"size: {shape['size']}",
    ]
    if shape.get("catalog_size"):
        lines.append(f"catalog_size: {shape['catalog_size']}")
    lines.append(f"tokens: {', '.join(shape.get('tokens') or [])}")
    lines.append(f"style: {shape['style']}")
    if shape.get("kind") == "gcp_card_icon":
        print(
            "note: GCP product icons must be Service Cards. "
            "Re-run with card=true in the --input-file request for paste-ready XML; "
            "do not paste style as a standalone icon.",
            file=sys.stderr,
        )
    return "\n".join(lines)


def _run_lookup(request: LookupRequest, common: dict[str, Any]) -> tuple[int, str]:
    if request.list_services:
        services = common["providers"][request.provider]["services"]
        return 0, "\n".join(sorted(services))
    if request.query is None:
        print("ERROR: query is required unless --list is used", file=sys.stderr)
        return 2, ""

    shape = resolve_shape(request.provider, request.query, common)
    if shape is None:
        print(f"MISS: {request.provider!r} {request.query!r}.", file=sys.stderr)
        return 2, ""
    if request.card:
        try:
            text = emit_gcp_service_card(
                shape,
                x=request.x,
                y=request.y,
                cell_id=request.cell_id,
                name=request.label,
                category=request.category,
            )
        except ValueError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 2, ""
        return 0, text
    if request.as_json:
        return 0, json.dumps(shape, indent=2)
    return 0, _text_shape(shape)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        requests = _requests_from_args(args)
    except UnsafeValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2

    common = load_common_shapes()
    json_payloads: list[Any] = []
    text_blocks: list[str] = []
    for request in requests:
        code, text = _run_lookup(request, common)
        if code != 0:
            return code
        if request.as_json:
            json_payloads.append(json.loads(text))
        else:
            text_blocks.append(text)
    if json_payloads:
        body: object = json_payloads[0] if len(json_payloads) == 1 else json_payloads
        print(json.dumps(body, indent=2))
        return 0
    print("\n\n".join(text_blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
