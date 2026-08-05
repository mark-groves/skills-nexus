#!/usr/bin/env python3
"""Shared catalog parsing for cloud-diagram shape lookup."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict

SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES_ROOT = SKILL_ROOT / "references"

PROVIDER_FILES = {
    "aws": REFERENCES_ROOT / "aws4-shapes.md",
    "azure": REFERENCES_ROOT / "azure-shapes.md",
    "gcp": REFERENCES_ROOT / "gcp-shapes.md",
}

COMMON_SHAPES_PATH = REFERENCES_ROOT / "common-shapes.json"
COMMON_SHAPES_SEED_PATH = REFERENCES_ROOT / "common-shapes.seed.json"

_STYLE_RE = re.compile(r"- \*\*Style:\*\* `(.+)`\s*$")
# Capture leading WxH; Azure headers append notes like "(adjust to content)".
_SIZE_RE = re.compile(r"- \*\*Size:\*\* (\d+x\d+|\S+)")
_TYPE_RE = re.compile(r"- \*\*Type:\*\* (.+)\s*$")
_AWS_RES_ICON_RE = re.compile(r"resIcon=mxgraph\.aws4\.[A-Za-z0-9_]+")
_AWS_GR_ICON_RE = re.compile(r"grIcon=mxgraph\.aws4\.[A-Za-z0-9_]+")
_AWS_SHAPE_RE = re.compile(r"shape=mxgraph\.aws4\.[A-Za-z0-9_]+")
# Shared shell shapes are not service identities; prefer resIcon/grIcon.
_AWS_GENERIC_SHAPES = frozenset({"mxgraph.aws4.resourceIcon", "mxgraph.aws4.group"})
_AZURE_IMAGE_RE = re.compile(r"image=img/lib/azure2/[^;]+")
_AZURE_GROUP_MARKER_KEYS = (
    "strokeColor",
    "strokeWidth",
    "dashed",
    "dashPattern",
    "fillColor",
)
_GCP_IMAGE_RE = re.compile(r"image=data:image/svg\+xml,[^;]+")
_GCP_SHAPE_RE = re.compile(r"(?:shape=)?mxgraph\.gcp2\.[A-Za-z0-9_]+")


class CatalogEntry(TypedDict):
    style: str | None
    size: str | None
    type: str | None


def normalize_query(value: str) -> str:
    return " ".join(value.strip().lower().split())


def is_container_style(style: str | None) -> bool:
    """True for group/swimlane styles used as architecture boundaries."""
    if not style:
        return False
    return (
        "container=1" in style
        or "grIcon=" in style
        or "shape=mxgraph.aws4.group" in style
        or style.startswith("swimlane;")
        or ";swimlane;" in style
    )


def is_resource_icon_style(style: str | None) -> bool:
    if not style:
        return False
    return "shape=mxgraph.aws4.resourceIcon" in style or "resIcon=" in style


def style_preference_rank(style: str | None) -> tuple[int, int]:
    """Higher ranks win when catalog titles collide.

    Header group/container styles share titles with later product icons
    (VPC, Availability Zone, Account, Azure Subnet). Architecture
    diagrams need the container. Prefer resourceIcon over bare product
    glyphs when both are icons.
    """
    return (
        1 if is_container_style(style) else 0,
        1 if is_resource_icon_style(style) else 0,
    )


def infer_shape_kind(provider: str, style: str | None, seed_kind: str | None = None) -> str:
    if seed_kind:
        return seed_kind
    if is_container_style(style):
        return "group"
    if provider == "gcp" and style and "data:image" in style:
        return "gcp_card_icon"
    return "icon"


def infer_shape_size(
    kind: str,
    catalog_size: str | None,
    default_icon_size: str = "50x50",
) -> str:
    if kind == "gcp_card_icon":
        return "30x30"
    if kind == "group" and catalog_size:
        match = re.match(r"(\d+x\d+)", catalog_size.strip())
        if match:
            return match.group(1)
    return default_icon_size


def parse_catalog(path: Path) -> dict[str, CatalogEntry]:
    text = path.read_text(encoding="utf-8")
    entries: dict[str, CatalogEntry] = {}
    parts = re.split(r"^### ", text, flags=re.M)
    for part in parts[1:]:
        lines = part.splitlines()
        title = lines[0].strip()
        style: str | None = None
        size: str | None = None
        entry_type: str | None = None
        for line in lines[1:]:
            if line.startswith("### ") or line.startswith("## "):
                break
            match = _STYLE_RE.match(line)
            if match:
                style = match.group(1)
                continue
            match = _SIZE_RE.match(line)
            if match:
                size = match.group(1)
                continue
            match = _TYPE_RE.match(line)
            if match:
                entry_type = match.group(1).strip()
        if not (style or entry_type):
            continue
        candidate: CatalogEntry = {
            "style": style,
            "size": size,
            "type": entry_type,
        }
        existing = entries.get(title)
        if existing is not None and style_preference_rank(style) < style_preference_rank(
            existing["style"]
        ):
            # Keep the better architecture default (group / resourceIcon).
            continue
        entries[title] = candidate
    return entries


def _azure_group_identity(style: str) -> str | None:
    """Fingerprint Azure swimlane containers that lack azure2 image tokens."""
    if not (style.startswith("swimlane") or ";swimlane;" in style):
        return None
    markers: list[str] = []
    for key in _AZURE_GROUP_MARKER_KEYS:
        match = re.search(rf"(?:^|;){re.escape(key)}=([^;]+)", style)
        if match:
            markers.append(f"{key}={match.group(1)}")
    if not markers:
        return None
    return "azure.group:" + ";".join(markers)


def extract_tokens(provider: str, title: str, style: str | None) -> list[str]:
    if not style:
        return []
    if provider == "aws":
        tokens = _AWS_RES_ICON_RE.findall(style)
        if tokens:
            return tokens
        group_icons = _AWS_GR_ICON_RE.findall(style)
        if group_icons:
            return group_icons
        return [
            token
            for token in _AWS_SHAPE_RE.findall(style)
            if token.removeprefix("shape=") not in _AWS_GENERIC_SHAPES
        ]
    if provider == "azure":
        images = _AZURE_IMAGE_RE.findall(style)
        if images:
            return images
        group_identity = _azure_group_identity(style)
        return [group_identity] if group_identity else []
    if provider == "gcp":
        if "data:image/svg+xml" in style:
            return ["data:image/svg+xml", title]
        return _GCP_SHAPE_RE.findall(style)
    raise ValueError(f"Unsupported provider: {provider}")


def _aws_identity_tokens(style: str) -> list[str]:
    """Canonical AWS identities from grIcon=, resIcon=, and non-generic shape=."""
    identities: list[str] = []
    seen: set[str] = set()
    for token in _AWS_GR_ICON_RE.findall(style):
        identity = token.removeprefix("grIcon=")
        if identity not in seen:
            seen.add(identity)
            identities.append(identity)
    for token in _AWS_RES_ICON_RE.findall(style):
        identity = token.removeprefix("resIcon=")
        if identity not in seen:
            seen.add(identity)
            identities.append(identity)
    for token in _AWS_SHAPE_RE.findall(style):
        identity = token.removeprefix("shape=")
        if identity in _AWS_GENERIC_SHAPES or identity in seen:
            continue
        seen.add(identity)
        identities.append(identity)
    return identities


def extract_identity_tokens(provider: str, style: str | None) -> list[str]:
    if not style:
        return []
    if provider == "aws":
        return _aws_identity_tokens(style)
    if provider == "azure":
        images = _AZURE_IMAGE_RE.findall(style)
        if images:
            return images
        group_identity = _azure_group_identity(style)
        return [group_identity] if group_identity else []
    if provider == "gcp":
        images = _GCP_IMAGE_RE.findall(style)
        return images or _GCP_SHAPE_RE.findall(style)
    raise ValueError(f"Unsupported provider: {provider}")


def load_common_shapes(path: Path = COMMON_SHAPES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_shape(
    provider: str,
    query: str,
    common_shapes: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    provider = normalize_query(provider)
    if provider not in PROVIDER_FILES:
        raise ValueError(f"Unsupported provider: {provider}")
    normalized = normalize_query(query)
    if not normalized:
        return None

    common = common_shapes or load_common_shapes()
    services = common.get("providers", {}).get(provider, {}).get("services", {})
    for service_id, service in services.items():
        names = [service_id, service.get("title", ""), *service.get("aliases", [])]
        if normalized in {normalize_query(name) for name in names if name}:
            return {"provider": provider, "id": service_id, **service}

    catalog = parse_catalog(PROVIDER_FILES[provider])
    exact = [
        (title, entry)
        for title, entry in catalog.items()
        if normalize_query(title) == normalized and entry["style"]
    ]
    matches = exact or [
        (title, entry)
        for title, entry in catalog.items()
        if normalized in normalize_query(title) and entry["style"]
    ]
    if not matches:
        return None
    title, entry = min(matches, key=lambda item: (len(item[0]), item[0].lower()))
    style = entry["style"]
    assert style is not None
    kind = infer_shape_kind(provider, style)
    size = infer_shape_size(kind, entry.get("size"))
    result = {
        "provider": provider,
        "id": normalize_query(title).replace(" ", "_"),
        "aliases": [],
        "title": title,
        "style": style,
        "size": size,
        "kind": kind,
        "tokens": extract_tokens(provider, title, style),
    }
    if entry["size"]:
        result["catalog_size"] = entry["size"]
    return result
