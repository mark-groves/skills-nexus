#!/usr/bin/env python3
"""Validate draw.io structure and provider shape fidelity."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from shape_catalog import PROVIDER_FILES, load_common_shapes, resolve_shape  # noqa: E402

PROVIDER_TOKENS = {
    "aws": ("mxgraph.aws4",),
    "azure": ("img/lib/azure2",),
    "gcp": ("data:image/svg+xml", "mxgraph.gcp2"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diagram", type=Path)
    parser.add_argument("--provider", choices=sorted(PROVIDER_FILES))
    parser.add_argument("--require-services", default="")
    return parser.parse_args(argv)


def _geometry(cell: ET.Element) -> ET.Element | None:
    for child in cell:
        if child.tag.rsplit("}", 1)[-1] == "mxGeometry":
            return child
    return None


def _skip_relative_offset(geometry: ET.Element) -> bool:
    if geometry.get("relative") != "1":
        return False
    return any(
        point.tag.rsplit("}", 1)[-1] == "mxPoint" and point.get("as") == "offset"
        for point in geometry
    )


def _bounds(geometry: ET.Element) -> tuple[float, float, float, float]:
    return (
        float(geometry.get("x", "0")),
        float(geometry.get("y", "0")),
        float(geometry.get("width", "0")),
        float(geometry.get("height", "0")),
    )


def _overlap_issues(cells: list[ET.Element]) -> list[str]:
    siblings: dict[str, list[tuple[ET.Element, tuple[float, float, float, float]]]] = defaultdict(
        list
    )
    for cell in cells:
        if cell.get("vertex") != "1" or cell.get("edge") == "1":
            continue
        geometry = _geometry(cell)
        if geometry is None or _skip_relative_offset(geometry):
            continue
        siblings[cell.get("parent", "")].append((cell, _bounds(geometry)))

    issues: list[str] = []
    for entries in siblings.values():
        for index, (left, left_bounds) in enumerate(entries):
            left_id = left.get("id", "<unknown>")
            for right, right_bounds in entries[index + 1 :]:
                right_id = right.get("id", "<unknown>")
                if left.get("parent") == right_id or right.get("parent") == left_id:
                    continue
                lx, ly, lw, lh = left_bounds
                rx, ry, rw, rh = right_bounds
                if lw <= 0 or lh <= 0 or rw <= 0 or rh <= 0:
                    continue
                overlap_width = min(lx + lw, rx + rw) - max(lx, rx)
                overlap_height = min(ly + lh, ry + rh) - max(ly, ry)
                if overlap_width > 0 and overlap_height > 0:
                    issues.append(f"overlap: {left_id} and {right_id}")
    return issues


def _generic_shape_issues(cells: list[ET.Element], provider: str) -> list[str]:
    provider_tokens = PROVIDER_TOKENS[provider]
    issues = []
    for cell in cells:
        if cell.get("vertex") != "1":
            continue
        style = cell.get("style", "")
        if any(token in style for token in provider_tokens):
            continue
        if "shape=mxgraph" in style or "image=img/lib" in style or "data:image" in style:
            continue
        if "grIcon=" in style or "resIcon=" in style:
            continue
        rounded = "rounded=1" in style or "shape=rectangle" in style
        if rounded and cell.get("value"):
            issues.append(
                f"generic shape used while provider shapes required: {cell.get('id', '<unknown>')}"
            )
    return issues


def collect_issues(
    diagram: Path,
    provider: str | None = None,
    require_services: list[str] | None = None,
) -> list[str]:
    try:
        root = ET.parse(diagram).getroot()
    except (OSError, ET.ParseError) as err:
        return [f"could not parse diagram: {err}"]

    cells = [cell for cell in root.iter() if cell.tag.rsplit("}", 1)[-1] == "mxCell"]
    issues: list[str] = []
    for cell in cells:
        if cell.get("edge") != "1":
            continue
        geometry = _geometry(cell)
        valid_geometry = geometry is not None and (
            geometry.get("relative") == "1" or geometry.get("as") == "geometry"
        )
        if not valid_geometry:
            issues.append(f"edge {cell.get('id', '<unknown>')}: missing mxGeometry child")

    issues.extend(_overlap_issues(cells))
    styles = [cell.get("style", "") for cell in cells]
    joined = "\n".join(styles)
    if provider and not any(token in joined for token in PROVIDER_TOKENS.get(provider, ())):
        issues.append(f"no provider shape tokens found for {provider}")

    if require_services:
        if provider is None:
            issues.append("--require-services needs --provider")
        else:
            common = load_common_shapes()
            for service_name in require_services:
                shape = resolve_shape(provider, service_name, common)
                if shape is None:
                    issues.append(f"unknown required service for lookup: {service_name}")
                    continue
                tokens = shape.get("tokens") or []
                if not tokens or not any(token in joined for token in tokens):
                    issues.append(f"missing provider shape for {service_name}")
            issues.extend(_generic_shape_issues(cells, provider))
    return issues


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    required = [service.strip() for service in args.require_services.split(",") if service.strip()]
    issues = collect_issues(args.diagram, args.provider, required or None)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    print(f"OK {args.diagram}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
