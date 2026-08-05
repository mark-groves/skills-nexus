#!/usr/bin/env python3
"""Emit paste-ready GCP Service Card XML from resolved catalog shapes."""

from __future__ import annotations

import html
import re
from typing import Any

_IMAGE_RE = re.compile(r"image=data:image/svg\+xml,[^;]+")
_CARD_STYLE = (
    "strokeColor=#dddddd;fillColor=#ffffff;shadow=1;strokeWidth=1;"
    "rounded=1;absoluteArcSize=1;arcSize=2;"
)
_ICON_STYLE_PREFIX = (
    "editableCssRules=.*;html=1;fontColor=#999999;shape=image;"
    "verticalLabelPosition=middle;verticalAlign=middle;labelPosition=right;"
    "align=left;spacingLeft=20;part=1;points=[];imageAspect=0;"
)


def extract_gcp_image_token(style: str | None) -> str | None:
    if not style:
        return None
    match = _IMAGE_RE.search(style)
    return match.group(0) if match else None


def card_width_for_label(name: str, category: str) -> int:
    """Pick a card width in the catalog's 160–190 range from label length.

    Service Card labels sit to the right of a 30x30 icon, so widths under
    160 clip common names like "Dashboards" / "Cloud Load Balancing".
    """
    longest = max(len(name.strip()), len(category.strip()), 1)
    if longest <= 14:
        return 160
    if longest <= 22:
        return 178
    return 190


def gcp_card_icon_style(image_token: str) -> str:
    token = image_token if image_token.startswith("image=") else f"image={image_token}"
    return f"{_ICON_STYLE_PREFIX}{token};"


def gcp_card_label(name: str, category: str) -> str:
    safe_name = html.escape(name.strip() or "Service", quote=True)
    safe_category = html.escape(category.strip() or "GCP", quote=True)
    return (
        f"&lt;font color=&quot;#000000&quot;&gt;{safe_name}&lt;/font&gt;&lt;br&gt;{safe_category}"
    )


def emit_gcp_service_card(
    shape: dict[str, Any],
    *,
    x: float = 200,
    y: float = 150,
    cell_id: str | None = None,
    name: str | None = None,
    category: str | None = None,
) -> str:
    """Return two mxCell elements for a GCP Service Card.

    Lookup styles are standalone catalog icons. Agents must not paste them
    as 30x30 vertices — wrap them with this emitter (or equivalent XML).
    """
    if shape.get("kind") != "gcp_card_icon":
        raise ValueError(
            f"emit_gcp_service_card requires kind=gcp_card_icon, got {shape.get('kind')!r}"
        )
    image_token = extract_gcp_image_token(shape.get("style"))
    if image_token is None:
        raise ValueError(f"no GCP data:image token in style for {shape.get('title')!r}")

    service_id = str(shape.get("id") or "service").replace(" ", "-")
    card_id = cell_id or f"card-{service_id}"
    icon_id = f"icon-{service_id}" if cell_id is None else f"icon-{cell_id.removeprefix('card-')}"
    title = str(shape.get("title") or service_id)
    primary = name or title
    secondary = category or title
    width = card_width_for_label(primary, secondary)
    label = gcp_card_label(primary, secondary)
    icon_style = gcp_card_icon_style(image_token)

    return (
        f'<mxCell id="{html.escape(card_id, quote=True)}" value="" '
        f'style="{_CARD_STYLE}" vertex="1" parent="1">\n'
        f'  <mxGeometry x="{x:g}" y="{y:g}" width="{width}" height="60" '
        f'as="geometry" />\n'
        f"</mxCell>\n"
        f'<mxCell id="{html.escape(icon_id, quote=True)}" value="{label}"\n'
        f'    style="{icon_style}"\n'
        f'    vertex="1" parent="{html.escape(card_id, quote=True)}">\n'
        f'  <mxGeometry width="30" height="30" relative="1" as="geometry">\n'
        f'    <mxPoint x="15" y="15" as="offset" />\n'
        f"  </mxGeometry>\n"
        f"</mxCell>"
    )
