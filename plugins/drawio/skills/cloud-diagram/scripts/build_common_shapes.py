#!/usr/bin/env python3
"""Build common-shapes.json from seed titles + catalog styles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from shape_catalog import (  # noqa: E402
    COMMON_SHAPES_PATH,
    COMMON_SHAPES_SEED_PATH,
    PROVIDER_FILES,
    extract_tokens,
    infer_shape_kind,
    infer_shape_size,
    parse_catalog,
)


def apply_style_patches(style: str, patches: dict[str, str] | None) -> str:
    """Replace or append style key=value pairs from the seed."""
    if not patches:
        return style
    updated = style
    for key, value in patches.items():
        pattern = re.compile(rf"(?:(?<=;)|^){re.escape(key)}=[^;]*;?")
        replacement = f"{key}={value};"
        if pattern.search(updated):
            updated = pattern.sub(replacement, updated, count=1)
        else:
            if not updated.endswith(";"):
                updated += ";"
            updated += replacement
    return updated


def build(
    seed_path: Path = COMMON_SHAPES_SEED_PATH,
    out_path: Path = COMMON_SHAPES_PATH,
) -> dict:
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    catalogs = {provider: parse_catalog(path) for provider, path in PROVIDER_FILES.items()}
    missing: list[str] = []
    providers_out: dict = {}
    for provider, pdata in seed["providers"].items():
        catalog = catalogs[provider]
        services_out: dict = {}
        for service_id, meta in pdata["services"].items():
            title = meta["title"]
            entry = catalog.get(title)
            if entry is None or not entry.get("style"):
                missing.append(f"{provider}:{service_id}:{title}")
                continue
            raw_style = entry["style"]
            if not isinstance(raw_style, str):
                missing.append(f"{provider}:{service_id}:{title}")
                continue
            style = apply_style_patches(raw_style, meta.get("style_patches"))
            kind = infer_shape_kind(provider, style, meta.get("kind"))
            default_size = seed.get("icon_size_default", "50x50")
            size = infer_shape_size(kind, entry.get("size"), default_size)
            services_out[service_id] = {
                "aliases": list(meta["aliases"]),
                "title": title,
                "style": style,
                "size": size,
                "catalog_size": entry.get("size"),
                "kind": kind,
                "tokens": extract_tokens(provider, title, style),
            }
        providers_out[provider] = {"services": services_out}
    if missing:
        raise RuntimeError("Missing catalog styles for: " + ", ".join(missing))
    payload = {
        "version": seed.get("version", 1),
        "icon_size_default": seed.get("icon_size_default", "50x50"),
        "providers": providers_out,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=COMMON_SHAPES_SEED_PATH)
    parser.add_argument("--out", type=Path, default=COMMON_SHAPES_PATH)
    args = parser.parse_args(argv)
    try:
        build(args.seed, args.out)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
