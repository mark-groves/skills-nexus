#!/usr/bin/env python3
"""Shared catalog parsing for cloud-diagram shape lookup."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
_SIZE_RE = re.compile(r"- \*\*Size:\*\* (\S+)\s*$")
_TYPE_RE = re.compile(r"- \*\*Type:\*\* (.+)\s*$")


def normalize_query(value: str) -> str:
    return " ".join(value.strip().lower().split())


def parse_catalog(path: Path) -> dict[str, dict[str, str | None]]:
    text = path.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str | None]] = {}
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
        if style or entry_type:
            entries[title] = {
                "style": style,
                "size": size,
                "type": entry_type,
            }
    return entries


def extract_tokens(provider: str, title: str, style: str | None) -> list[str]:
    if not style:
        return []
    tokens: list[str] = []
    if provider == "aws":
        for match in re.finditer(r"resIcon=mxgraph\.aws4\.[A-Za-z0-9_]+", style):
            tokens.append(match.group(0))
        if not tokens:
            for match in re.finditer(r"shape=mxgraph\.aws4\.[A-Za-z0-9_]+", style):
                tokens.append(match.group(0))
    elif provider == "azure":
        for match in re.finditer(r"image=img/lib/azure2/[^;]+", style):
            tokens.append(match.group(0))
    elif provider == "gcp":
        if "data:image/svg+xml" in style:
            tokens.extend(["data:image/svg+xml", title])
        for match in re.finditer(r"mxgraph\.gcp2\.[A-Za-z0-9_]+", style):
            tokens.append(match.group(0))
    return tokens


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
    kind = "gcp_card_icon" if provider == "gcp" and "data:image" in style else "icon"
    size = "30x30" if kind == "gcp_card_icon" else "50x50"
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
