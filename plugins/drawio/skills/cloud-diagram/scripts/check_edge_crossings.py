#!/usr/bin/env python3
"""Flag edges that draw.io routes through an icon or service card.

Reads the diagram for cell roles and the official draw.io CLI SVG export
(scripts/export_diagram.sh) for the routed edge paths and icon boxes, so
no routing is re-implemented here. Exits 1 when an edge passes through
an icon it does not connect to.
"""

from __future__ import annotations

import argparse
import html
import itertools
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

SVG_NS = "{http://www.w3.org/2000/svg}"
Point = tuple[float, float]
Box = tuple[float, float, float, float]

# Strokes this close to an icon edge graze it rather than cross it.
EDGE_MARGIN = 2.0
# Icons up to this size whose centre sits on the route are annotations
# drawn on the link (encryption glyphs, numbered step badges).
ANNOTATION_MAX_SIZE = 32.0
ANNOTATION_CENTRE_TOLERANCE = 3.0

_PATH_TOKEN_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_PATH_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Crossing:
    edge: str
    icon: str
    message: str


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def path_points(d: str) -> list[Point]:
    """Absolute end and control points of an SVG path."""
    points: list[Point] = []
    x = y = 0.0
    command = ""
    args: list[float] = []

    def flush() -> None:
        nonlocal x, y
        relative = command.islower()
        op = command.upper()
        values = args[:]
        if op == "H":
            x = values[0] + (x if relative else 0.0)
        elif op == "V":
            y = values[0] + (y if relative else 0.0)
        elif op == "A":
            x, y = (values[5] + x, values[6] + y) if relative else (values[5], values[6])
        else:
            base_x, base_y = (x, y) if relative else (0.0, 0.0)
            for i in range(0, len(values), 2):
                points.append((values[i] + base_x, values[i + 1] + base_y))
            x, y = points[-1]
            return
        points.append((x, y))

    for token in _PATH_TOKEN_RE.findall(d):
        if token.isalpha():
            command, args = token, []
            continue
        args.append(float(token))
        arity = _PATH_ARITY[command.upper()]
        if len(args) == arity:
            flush()
            args = []
            if command in "Mm":
                command = "l" if command == "m" else "L"
    return points


def _element_points(element: ET.Element) -> list[Point]:
    tag = _local(element.tag)
    if tag in ("rect", "image", "svg"):
        x, y = float(element.get("x", 0)), float(element.get("y", 0))
        return [(x, y), (x + float(element.get("width", 0)), y + float(element.get("height", 0)))]
    if tag == "ellipse":
        cx, cy = float(element.get("cx", 0)), float(element.get("cy", 0))
        rx, ry = float(element.get("rx", 0)), float(element.get("ry", 0))
        return [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    if tag == "path" and element.get("d"):
        return path_points(element.get("d", ""))
    return []


def shape_box(group: ET.Element) -> Box | None:
    """Bounding box of a cell's drawing, excluding its label."""
    points: list[Point] = []
    stack = [group]
    while stack:
        element = stack.pop()
        tag = _local(element.tag)
        if tag in ("switch", "foreignObject", "text"):
            continue
        points.extend(_element_points(element))
        # Nested symbol SVGs use their own coordinate system.
        if tag != "svg" or element is group:
            stack.extend(element)
    if not points:
        return None
    xs, ys = zip(*points, strict=True)
    return (min(xs), min(ys), max(xs), max(ys))


def _segment_hits_box(p: Point, q: Point, box: Box, margin: float) -> bool:
    x0, y0, x1, y1 = box[0] + margin, box[1] + margin, box[2] - margin, box[3] - margin
    if x0 >= x1 or y0 >= y1:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for denominator, numerator in (
        (-dx, p[0] - x0),
        (dx, x1 - p[0]),
        (-dy, p[1] - y0),
        (dy, y1 - p[1]),
    ):
        if denominator == 0:
            if numerator < 0:
                return False
            continue
        t = numerator / denominator
        if denominator < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _distance_to_segment(point: Point, p: Point, q: Point) -> float:
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = dx * dx + dy * dy
    t = (
        0.0
        if length == 0
        else max(0.0, min(1.0, ((point[0] - p[0]) * dx + (point[1] - p[1]) * dy) / length))
    )
    return math.hypot(point[0] - (p[0] + t * dx), point[1] - (p[1] + t * dy))


def _inside(point: Point, box: Box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _is_annotation(box: Box, route: list[Point]) -> bool:
    if max(box[2] - box[0], box[3] - box[1]) > ANNOTATION_MAX_SIZE:
        return False
    centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    return any(
        _distance_to_segment(centre, p, q) <= ANNOTATION_CENTRE_TOLERANCE
        for p, q in itertools.pairwise(route)
    )


def _load_cells(path: Path) -> dict[str, ET.Element]:
    root = ET.parse(path).getroot()
    return {cell.get("id", ""): cell for cell in root.iter("mxCell") if cell.get("id")}


def _is_obstacle(cell: ET.Element, cells: dict[str, ET.Element], parents: set[str]) -> bool:
    """A leaf icon or a whole service card; never a container, label, or card part."""
    if cell.get("vertex") != "1":
        return False
    style = cell.get("style", "") or ""
    keys = {part.split("=", 1)[0] for part in style.split(";")}
    parent = cells.get(cell.get("parent", ""))
    if parent is not None and parent.get("edge") == "1":
        return False
    if (
        "part=1" in style.split(";")
        or "text" in keys
        or "swimlane" in keys
        or "container=1" in style
    ):
        return False
    if "mxgraph.aws4.group" in style or "mxgraph.gcp2.group" in style:
        return False
    if cell.get("id") in parents:
        children = (c for c in cells.values() if c.get("parent") == cell.get("id"))
        return all("part=1" in (c.get("style", "") or "").split(";") for c in children)
    return "image" in keys or "shape" in keys


def _lineage(cells: dict[str, ET.Element], cell_id: str | None) -> set[str]:
    """A cell with its ancestors and descendants: the shapes an edge may touch at that end."""
    if not cell_id or cell_id not in cells:
        return set()
    down = {cell_id}
    grown = True
    while grown:
        grown = False
        for key, cell in cells.items():
            if cell.get("parent") in down and key not in down:
                down.add(key)
                grown = True
    lineage = set(down)
    current = cells[cell_id]
    while current.get("parent") in cells:
        lineage.add(current.get("parent", ""))
        current = cells[current.get("parent", "")]
    return lineage


def _label(cells: dict[str, ET.Element], cell_id: str | None) -> str:
    if not cell_id or cell_id not in cells:
        return "unattached"
    cell = cells[cell_id]
    text = html.unescape(_TAG_RE.sub(" ", (cell.get("value") or "").replace("<br>", " ")))
    text = " ".join(text.split())
    if not text:
        text = next(
            (
                " ".join(html.unescape(_TAG_RE.sub(" ", c.get("value") or "")).split())
                for c in cells.values()
                if c.get("parent") == cell_id and c.get("value")
            ),
            "",
        )
    return text or cell_id


class ExportError(ValueError):
    pass


def find_crossings(diagram: Path, svg: Path) -> list[Crossing]:
    cells = _load_cells(diagram)
    groups = {
        g.get("data-cell-id"): g for g in ET.parse(svg).getroot().iter() if g.get("data-cell-id")
    }
    edges = [cid for cid, cell in cells.items() if cell.get("edge") == "1"]
    if edges and not any(cid in groups for cid in edges):
        raise ExportError(
            f"{svg} has no draw.io cell ids; export it with scripts/export_diagram.sh"
        )

    parents = {cell.get("parent", "") for cell in cells.values()}
    boxes: dict[str, Box] = {}
    for cid, cell in cells.items():
        group = groups.get(cid)
        drawing = next(iter(group), None) if group is not None else None
        box = shape_box(drawing) if drawing is not None else None
        if box is not None and _is_obstacle(cell, cells, parents):
            boxes[cid] = box

    crossings = []
    for eid in edges:
        group = groups.get(eid)
        path = None
        if group is not None:
            path = next((p for p in group.iter(f"{SVG_NS}path") if p.get("fill") == "none"), None)
        if path is None:
            continue
        route = path_points(path.get("d", ""))
        edge = cells[eid]
        source, target = edge.get("source"), edge.get("target")
        exempt = _lineage(cells, source) | _lineage(cells, target)
        loose_ends = [
            end for end, attached in ((route[0], source), (route[-1], target)) if not attached
        ]
        for icon, box in boxes.items():
            if icon in exempt or any(_inside(end, box) for end in loose_ends):
                continue
            if not any(
                _segment_hits_box(p, q, box, EDGE_MARGIN) for p, q in itertools.pairwise(route)
            ):
                continue
            if _is_annotation(box, route):
                continue
            crossings.append(
                Crossing(
                    eid,
                    icon,
                    f"edge {eid} ({_label(cells, source)} -> {_label(cells, target)}) "
                    f"passes through icon {icon} ({_label(cells, icon)})",
                )
            )
    return crossings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diagram", type=Path, help="The .drawio file.")
    parser.add_argument("svg", type=Path, help="Its SVG from scripts/export_diagram.sh.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        crossings = find_crossings(args.diagram, args.svg)
    except (ET.ParseError, OSError, ExportError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for crossing in crossings:
        print(crossing.message)
    if crossings:
        return 1
    print(f"OK {args.diagram}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
