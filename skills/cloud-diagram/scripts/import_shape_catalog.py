#!/usr/bin/env python3
"""Import generated drawio-shapes fragments into cloud-diagram references."""

from __future__ import annotations

import argparse
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES_ROOT = SKILL_ROOT / "references"
GENERATED_MARKER = "<!-- GENERATED BELOW -->"

PROVIDERS = {
    "AWS4": {
        "library": "AWS4",
        "target_name": "aws4-shapes.md",
        "fragment_name": "aws4-shapes.generated.md",
    },
    "GCP2": {
        "library": "GCP2",
        "target_name": "gcp-shapes.md",
        "fragment_name": "gcp-shapes.generated.md",
    },
    "Azure2": {
        "library": "Azure2",
        "target_name": "azure-shapes.md",
        "fragment_name": "azure-shapes.generated.md",
    },
}

ALIASES = {
    "all": "all",
    "aws": "AWS4",
    "aws4": "AWS4",
    "azure": "Azure2",
    "azure2": "Azure2",
    "gcp": "GCP2",
    "gcp2": "GCP2",
}


def require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Missing {description}: {path}")
    return path


def count_entries(fragment_text: str) -> int:
    return sum(1 for line in fragment_text.splitlines() if line.startswith("### "))


def validate_fragment(path: Path) -> str:
    text = require_file(path, "generated fragment").read_text(encoding="utf-8")
    normalized = text.strip()
    if not normalized:
        raise RuntimeError(f"Fragment is empty: {path}")
    if GENERATED_MARKER in normalized:
        raise RuntimeError(f"Fragment must not include {GENERATED_MARKER}: {path}")
    if "## " not in normalized or "### " not in normalized:
        raise RuntimeError(f"Fragment format is invalid or empty: {path}")
    return normalized + "\n"


def summary_text(library: str, final_count: int) -> str:
    if library == "AWS4":
        return (
            f"A complete catalog of {final_count} unique AWS4 shapes extracted from the\n"
            "`mxgraph.aws4` stencil library. Every style string is copy-paste ready\n"
            "for draw.io XML generation."
        )
    if library == "GCP2":
        return (
            "Complete catalog of unique Google Cloud Platform shapes extracted\n"
            f"from the jgraph/drawio GCP2 and GCPIcons sidebar libraries ({final_count} entries)."
        )
    if library == "Azure2":
        return (
            f"A complete catalog of {final_count} unique Azure2 service shapes for draw.io\n"
            "diagram generation using SVG image references."
        )
    raise RuntimeError(f"Unsupported library: {library}")


def refresh_header_summary(library: str, header: str, final_count: int) -> str:
    paragraphs = header.strip().split("\n\n")
    if len(paragraphs) < 2:
        raise RuntimeError(f"Could not refresh header summary for {library}")
    paragraphs[1] = summary_text(library, final_count)
    return "\n\n".join(paragraphs) + "\n"


def assemble_import(target_path: Path, fragment_text: str, library: str) -> str:
    target_text = require_file(target_path, "bundled reference file").read_text(encoding="utf-8")
    marker = f"{GENERATED_MARKER}\n"
    if marker not in target_text:
        raise RuntimeError(f"Missing {GENERATED_MARKER} in {target_path}")

    header, _ = target_text.split(marker, 1)
    refreshed_header = refresh_header_summary(library, header, count_entries(fragment_text))
    return refreshed_header.rstrip() + "\n\n" + GENERATED_MARKER + "\n\n" + fragment_text.strip() + "\n"


def normalize_provider_args(values: list[str]) -> list[str]:
    if not values:
        return list(PROVIDERS)

    normalized = []
    for value in values:
        key = ALIASES.get(value.lower())
        if key is None:
            raise SystemExit(f"Unsupported provider: {value}")
        if key == "all":
            return list(PROVIDERS)
        if key not in normalized:
            normalized.append(key)
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import generated drawio-shapes fragments into cloud-diagram references."
    )
    parser.add_argument(
        "providers",
        nargs="*",
        help="Providers to import: aws, gcp, azure, or all (default: all)",
    )
    parser.add_argument(
        "--from-dir",
        required=True,
        help="Directory containing *.generated.md fragments",
    )
    parser.add_argument(
        "--references-dir",
        default=str(REFERENCES_ROOT),
        help="Directory containing bundled target references (default: cloud-diagram/references)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate fragments and target references without writing files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from_dir = Path(args.from_dir).resolve()
    references_dir = Path(args.references_dir).resolve()

    try:
        planned_imports = []
        for provider_key in normalize_provider_args(args.providers):
            config = PROVIDERS[provider_key]
            fragment_path = from_dir / config["fragment_name"]
            target_path = references_dir / config["target_name"]
            fragment_text = validate_fragment(fragment_path)
            rendered = assemble_import(target_path, fragment_text, config["library"])
            planned_imports.append((config, fragment_path, target_path, rendered))

        for config, fragment_path, target_path, rendered in planned_imports:
            if args.check_only:
                print(f"{config['library']}: validated {fragment_path} against {target_path}")
                continue

            target_path.write_text(rendered, encoding="utf-8")
            print(f"{config['library']}: imported {fragment_path} into {target_path}")
    except RuntimeError as err:
        raise SystemExit(str(err))


if __name__ == "__main__":
    main()
