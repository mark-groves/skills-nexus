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

from gcp_card import is_gcp_service_card_style  # noqa: E402
from shape_catalog import (  # noqa: E402
    PROVIDER_FILES,
    extract_identity_tokens,
    load_common_shapes,
    normalize_query,
    parse_catalog,
    resolve_shape,
)

PROVIDER_TOKENS = {
    "aws": ("mxgraph.aws4",),
    # azure2 icons plus swimlane architecture groups (Subnet, VNet, …).
    "azure": ("img/lib/azure2", "swimlane;"),
    # Positive GCP detection still accepts catalog data:image icons and gcp2.
    "gcp": ("data:image/svg+xml", "mxgraph.gcp2"),
}

# Library prefixes owned by each provider. Foreign checks reject other
# providers' markers unless listed in --allow-providers. Generic
# data:image/svg+xml is never used as GCP evidence — catalog-backed
# GCP product images are checked separately.
PROVIDER_LIBRARY_TOKENS = {
    "aws": ("mxgraph.aws4",),
    "azure": ("img/lib/azure2",),
    "gcp": ("mxgraph.gcp2",),
}

_GCP_IMAGE_TOKEN_RE = re.compile(r"image=data:image/svg\+xml,[^;\s]+")
_GCP_CATALOG_IMAGE_TOKENS: frozenset[str] | None = None


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
    parser.add_argument(
        "--allow-providers",
        default="",
        help=(
            "Comma-separated extra providers whose shapes are allowed "
            "(multi-cloud diagrams). Skips foreign-provider checks for those."
        ),
    )
    parser.add_argument("--require-services", default="")
    return parser.parse_args(argv)


def _gcp_catalog_image_tokens() -> frozenset[str]:
    """Lazy-load catalog-backed GCP data:image identity tokens."""
    global _GCP_CATALOG_IMAGE_TOKENS
    if _GCP_CATALOG_IMAGE_TOKENS is None:
        tokens: set[str] = set()
        for entry in parse_catalog(PROVIDER_FILES["gcp"]).values():
            for token in extract_identity_tokens("gcp", entry.get("style")):
                if token.startswith("image=data:image/svg+xml,"):
                    tokens.add(token)
        _GCP_CATALOG_IMAGE_TOKENS = frozenset(tokens)
    return _GCP_CATALOG_IMAGE_TOKENS


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


def _fully_contains(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
) -> bool:
    """True when outer strictly covers inner (intentional layered backgrounds)."""
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    if iw <= 0 or ih <= 0 or ow <= 0 or oh <= 0:
        return False
    return (
        ox <= ix
        and oy <= iy
        and ox + ow >= ix + iw
        and oy + oh >= iy + ih
        and (ow * oh) > (iw * ih)
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
                # GCP (and similar) place platform/group/card shells as siblings
                # with visual nesting; full containment is not a layout defect.
                if _fully_contains(left_bounds, right_bounds) or _fully_contains(
                    right_bounds, left_bounds
                ):
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


def _foreign_gcp_catalog_image_issues(joined_styles: str, provider: str) -> list[str]:
    """Flag catalog GCP product icons used under a non-GCP provider."""
    catalog = _gcp_catalog_image_tokens()
    for token in _GCP_IMAGE_TOKEN_RE.findall(joined_styles):
        if token in catalog:
            return [f"foreign provider shape token for {provider}: GCP catalog image"]
    return []


def _foreign_provider_issues(
    joined_styles: str,
    provider: str,
    allow_providers: set[str] | None = None,
) -> list[str]:
    allowed = {provider, *(allow_providers or set())}
    issues: list[str] = []
    for other, tokens in PROVIDER_LIBRARY_TOKENS.items():
        if other in allowed:
            continue
        for token in tokens:
            if token in joined_styles:
                issues.append(f"foreign provider shape token for {provider}: {token}")
    if "gcp" not in allowed:
        issues.extend(_foreign_gcp_catalog_image_issues(joined_styles, provider))
    return issues


def _gcp_service_card_issues(
    cells: list[ET.Element],
    required_shapes: list[dict],
) -> list[str]:
    """Require GCP product icons to sit in Service Cards (part=1 children)."""
    cells_by_id = {cell.get("id"): cell for cell in cells if cell.get("id")}
    issues: list[str] = []
    for shape in required_shapes:
        if shape.get("kind") != "gcp_card_icon":
            continue
        expected = set(extract_identity_tokens("gcp", shape.get("style")))
        if not expected:
            continue
        matched = False
        for cell in cells:
            style = cell.get("style", "")
            tokens = set(extract_identity_tokens("gcp", style))
            if not expected.intersection(tokens):
                continue
            if "part=1" not in style:
                continue
            parent_id = cell.get("parent")
            if parent_id in {None, "", "0", "1"}:
                continue
            parent = cells_by_id.get(parent_id)
            if (
                parent is not None
                and parent.get("vertex") == "1"
                and is_gcp_service_card_style(parent.get("style"))
            ):
                matched = True
                break
        if not matched:
            title = shape.get("title") or shape.get("id") or "<unknown>"
            issues.append(f"GCP service must use Service Card (part=1 icon child): {title}")
    return issues


def _azure_group_issues(
    cells: list[ET.Element],
    required_shapes: list[dict],
    actual_tokens: set[str],
) -> list[str]:
    """Flag Azure group services drawn as azure2 product icons."""
    issues: list[str] = []
    for shape in required_shapes:
        if shape.get("kind") != "group":
            continue
        expected = set(extract_identity_tokens("azure", shape.get("style")))
        if expected and expected.intersection(actual_tokens):
            continue
        names = _label_names(shape)
        title = shape.get("title") or shape.get("id") or "<unknown>"
        for cell in cells:
            if cell.get("vertex") != "1":
                continue
            style = cell.get("style", "")
            if "img/lib/azure2/" not in style:
                continue
            label = _visible_label(cell.get("value", ""))
            if any(label == name or label.startswith(f"{name} ") for name in names):
                issues.append(
                    f"Azure group must use swimlane container, not azure2 product icon: {title}"
                )
                break
    return issues


def collect_issues(
    diagram: Path,
    provider: str | None = None,
    require_services: list[str] | None = None,
    allow_providers: list[str] | None = None,
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
    if provider:
        issues.extend(_foreign_provider_issues(joined, provider, set(allow_providers or [])))

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
            if provider == "gcp":
                issues.extend(_gcp_service_card_issues(cells, required_shapes))
            if provider == "azure":
                issues.extend(_azure_group_issues(cells, required_shapes, actual_tokens))
    return issues


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    required = [service.strip() for service in args.require_services.split(",") if service.strip()]
    allowed = [name.strip() for name in args.allow_providers.split(",") if name.strip()]
    unknown = [name for name in allowed if name not in PROVIDER_FILES]
    if unknown:
        print(
            f"ERROR: unknown --allow-providers value(s): {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 2
    issues = collect_issues(
        args.diagram,
        args.provider,
        required or None,
        allow_providers=allowed or None,
    )
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    print(f"OK {args.diagram}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
