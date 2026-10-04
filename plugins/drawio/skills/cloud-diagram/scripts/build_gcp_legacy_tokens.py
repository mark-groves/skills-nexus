#!/usr/bin/env python3
"""Build gcp-legacy-tokens.json from an older gcp-shapes.md.

Each GCP image token in the old catalog that the current catalog no longer
carries is mapped, by digest, to the current title that replaced it. The
validator uses the map to upgrade old diagrams with a warning.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from shape_catalog import (  # noqa: E402
    GCP_LEGACY_TOKENS_PATH,
    PROVIDER_FILES,
    extract_identity_tokens,
    parse_catalog,
    token_digest,
)

_IMAGE_PREFIX = "image=data:image/svg+xml,"
_FAMILY_SUFFIX = " (GCPIcons)"


def _image_tokens(style: str | None) -> list[str]:
    return [t for t in extract_identity_tokens("gcp", style) if t.startswith(_IMAGE_PREFIX)]


def build(old_catalog: Path, source: str, out_path: Path = GCP_LEGACY_TOKENS_PATH) -> dict:
    current = parse_catalog(PROVIDER_FILES["gcp"])
    current_tokens = {
        token for entry in current.values() for token in _image_tokens(entry["style"])
    }
    tokens: dict[str, str] = {}
    unmapped: list[str] = []
    for title, entry in parse_catalog(old_catalog).items():
        for token in _image_tokens(entry["style"]):
            if token in current_tokens:
                continue
            target = title if title in current else title.removesuffix(_FAMILY_SUFFIX)
            if target not in current or not _image_tokens(current[target]["style"]):
                unmapped.append(title)
                continue
            tokens[token_digest(token)] = target
    if unmapped:
        raise RuntimeError("No current GCP image icon for: " + ", ".join(sorted(set(unmapped))))
    payload = {"source": source, "tokens": dict(sorted(tokens.items()))}
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("old_catalog", type=Path, help="An older gcp-shapes.md")
    parser.add_argument("--source", required=True, help="Where the old catalog came from")
    parser.add_argument("--out", type=Path, default=GCP_LEGACY_TOKENS_PATH)
    args = parser.parse_args(argv)
    try:
        payload = build(args.old_catalog, args.source, args.out)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Wrote {len(payload['tokens'])} legacy tokens to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
