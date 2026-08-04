#!/usr/bin/env python3
"""Validate draw.io structure and provider shape fidelity."""

from __future__ import annotations

import argparse
import html
import re
import sys
import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
from collections import defaultdict
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from shape_catalog import (  # noqa: E402
    PROVIDER_FILES,
    extract_identity_tokens,
    load_common_shapes,
    normalize_query,
    resolve_shape,
)

PROVIDER_TOKENS = {
    "aws": ("mxgraph.aws4",),
    "azure": ("img/lib/azure2",),
    "gcp": ("data:image/svg+xml", "mxgraph.gcp2"),
}


def _parse_xml(path: Path) -> ET.Element:
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data

    def reject_declaration(*_args: object) -> None:
        raise ValueError("DTD and entity declarations are not allowed")

    def reject_external_entity(*_args: object) -> int:
        raise ValueError("External entities are not allowed")

    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_external_entity
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            parser.Parse(chunk, False)
    parser.Parse(b"", True)
    return builder.close()


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


def _provider_backed_cells(cells: list[ET.Element], provider: str) -> set[str]:
    cells_by_id = {cell.get("id"): cell for cell in cells if cell.get("id")}
    backed: set[str] = set()
    for cell in cells:
        style = cell.get("style", "")
        if not any(token in style for token in PROVIDER_TOKENS[provider]):
            continue
        cell_id = cell.get("id")
        while cell_id and cell_id not in backed:
            backed.add(cell_id)
            parent = cells_by_id.get(cell_id)
            cell_id = parent.get("parent") if parent is not None else None
    return backed


def _label_names(shape: dict) -> set[str]:
    return {
        normalize_query(name)
        for name in [shape.get("id", ""), shape.get("title", ""), *shape.get("aliases", [])]
        if name
    }


def _visible_label(value: str) -> str:
    return normalize_query(html.unescape(re.sub(r"<[^>]+>", " ", value)))


def _generic_shape_issues(
    cells: list[ET.Element],
    provider: str,
    required_shapes: list[dict],
) -> list[str]:
    backed = _provider_backed_cells(cells, provider)
    required_names = set().union(*(_label_names(shape) for shape in required_shapes))
    issues: list[str] = []
    for cell in cells:
        style = cell.get("style", "")
        cell_id = cell.get("id", "<unknown>")
        if cell.get("vertex") != "1" or cell_id in backed:
            continue
        if "rounded=1" not in style and "shape=rectangle" not in style:
            continue
        label = _visible_label(cell.get("value", ""))
        if any(label == name or label.startswith(f"{name} ") for name in required_names):
            issues.append(f"generic shape used while provider shapes required: {cell_id}")
    return issues


def collect_issues(
    diagram: Path,
    provider: str | None = None,
    require_services: list[str] | None = None,
) -> list[str]:
    try:
        root = _parse_xml(diagram)
    except (OSError, ValueError, expat.ExpatError) as err:
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
            actual_tokens = {
                token for style in styles for token in extract_identity_tokens(provider, style)
            }
            required_shapes: list[dict] = []
            for service_name in require_services:
                shape = resolve_shape(provider, service_name, common)
                if shape is None:
                    issues.append(f"unknown required service for lookup: {service_name}")
                    continue
                required_shapes.append(shape)
                expected_tokens = set(extract_identity_tokens(provider, shape.get("style")))
                if not expected_tokens.intersection(actual_tokens):
                    issues.append(f"missing provider shape for {service_name}")
            issues.extend(_generic_shape_issues(cells, provider, required_shapes))
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
