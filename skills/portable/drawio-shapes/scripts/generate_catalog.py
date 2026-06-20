#!/usr/bin/env python3
"""Generate import-ready cloud-diagram catalog fragments from extracted JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKING_ROOT = SKILL_ROOT / "working"

GCP_STENCIL_BASE = (
    "sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=#4285F4;"
    "strokeColor=none;dashed=0;verticalLabelPosition=bottom;"
    "verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;"
    "aspect=fixed;shape={stencil};"
)
GCP_VERTEX_ICON_BASE = (
    "editableCssRules=.*;html=1;shape=image;verticalLabelPosition=bottom;"
    "verticalAlign=top;imageAspect=1;aspect=fixed;image=data:image/svg+xml,{b64};"
)
GCP_EDGE_BASE = (
    "edgeStyle=orthogonalEdgeStyle;fontSize=12;html=1;endArrow=blockThin;"
    "endFill=1;rounded=0;strokeWidth=2;endSize=4;startSize=4;"
)
GCP_ZONE_BASE = (
    "sketch=0;points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],"
    "[1,0.25,0],[1,0.5,0],[1,0.75,0],[1,1,0],[0.75,1,0],[0.5,1,0],"
    "[0.25,1,0],[0,1,0],[0,0.75,0],[0,0.5,0],[0,0.25,0]];rounded=1;"
    "absoluteArcSize=1;arcSize=2;html=1;strokeColor=none;gradientColor=none;"
    "shadow=0;dashed=0;fontSize=12;fontColor=#9E9E9E;align=left;"
    "verticalAlign=top;spacing=10;spacingTop=-4;whiteSpace=wrap;"
)
GCP_ZONE_FILLS = {
    "User 1 (Default)": "#ffffff",
    "Infrastructure System": "#F3E5F5",
    "colo / dc / on-premises": "#EFEBE9",
    "System 1": "#F1F8E9",
    "External SaaS Providers": "#FFEBEE",
    "External Data Sources": "#FFF8E1",
    "External Infrastructure 3rd party": "#E0F2F1",
    "External Infrastructure 1st party": "#E1F5FE",
    "Title bar": "#E8EAF6",
    "Note": "#FFF9C4",
}
GCP_EDGE_SUFFIXES = {
    "Primary Path": "dashed=0;strokeColor=#4284F3;",
    "Optional Primary Path": "dashed=1;dashPattern=1 3;strokeColor=#4284F3;",
    "Secondary Path": "dashed=0;strokeColor=#9E9E9E;",
    "Optional Secondary Path": "dashed=1;dashPattern=1 3;strokeColor=#9E9E9E;",
    "Success Status": "strokeColor=#34A853;dashed=0;",
    "Failure Status": "strokeColor=#EA4335;dashed=0;",
}

DISPLAY_NAMES = {
    "AWS4": {
        "GeneralResources": "General Resources",
        "ApplicationIntegration": "Application Integration",
        "ARVR": "AR / VR",
        "CloudFinancialManagement": "Cloud Financial Management",
        "BusinessApplications": "Business Applications",
        "ContactCenter": "Contact Center",
        "CustomerEnablement": "Customer Enablement",
        "CustomerEngagement": "Customer Engagement",
        "DeveloperTools": "Developer Tools",
        "EndUserComputing": "End User Computing",
        "FrontEndWebMobile": "Front-End Web & Mobile",
        "InternetOfThings": "Internet of Things",
        "ArtificialIntelligence": "Artificial Intelligence",
        "ManagementGovernance": "Management & Governance",
        "MediaServices": "Media Services",
        "MigrationModernization": "Migration & Modernization",
        "NetworkContentDelivery": "Network & Content Delivery",
        "QuantumTechnologies": "Quantum Technologies",
        "SecurityIdentityCompliance": "Security, Identity & Compliance",
    },
    "Azure2": {
        "AIMachineLearning": "AI and ML",
        "AppServices": "App Services",
        "AzureStack": "Azure Stack",
        "AzureVMwareSolution": "Azure VMware Solution",
        "CXP": "CXP",
        "DevOps": "DevOps",
        "HybridAndMulticloud": "Hybrid and Multicloud",
        "IOT": "IoT",
        "ManagementGovernance": "Management & Governance",
        "MixedReality": "Mixed Reality",
        "PowerPlatform": "Power Platform",
    },
    "GCP2": {
        "GeneralIcons": "General Icons",
        "ServiceCards": "Service Cards",
        "UserDeviceCards": "User Device Cards",
        "APIManagement": "API Management",
        "DataAnalytics": "Data Analytics",
        "DataTransfer": "Data Transfer",
        "CloudAI": "Cloud AI",
        "InternetOfThings": "Internet of Things",
        "ManagementTools": "Management Tools",
        "DeveloperTools": "Developer Tools",
        "ExpandedProductCards": "Expanded Product Cards",
        "ProductCards": "Product Cards",
        "IconsAIAndMachineLearning": "Icons: AI and Machine Learning",
        "IconsCompute": "Icons: Compute",
        "IconsDataAnalytics": "Icons: Data Analytics",
        "IconsOperations": "Icons: Operations",
        "IconsNetworking": "Icons: Networking",
        "IconsCICD": "Icons: CI/CD",
        "IconsIntegrationServices": "Icons: Integration Services",
        "IconsAPIManagement": "Icons: API Management",
        "IconsInternetOfThings": "Icons: Internet of Things",
        "IconsDatabases": "Icons: Databases",
        "IconsStorage": "Icons: Storage",
        "IconsSecurity": "Icons: Security",
        "IconsServerless": "Icons: Serverless",
        "IconsMigration": "Icons: Migration",
        "IconsHybridAndMultiCloud": "Icons: Hybrid and Multi-Cloud",
        "IconsOpenSourceIcons": "Icons: Open Source Icons",
        "GCPIconsAIandMachineLearning": "GCPIcons: AI and Machine Learning",
        "GCPIconsAPIManagement": "GCPIcons: API Management",
        "GCPIconsCompute": "GCPIcons: Compute",
        "GCPIconsDataAnalytics": "GCPIcons: Data Analytics",
        "GCPIconsDatabases": "GCPIcons: Databases",
        "GCPIconsDeveloperTools": "GCPIcons: Developer Tools",
        "GCPIconsExpandedProductCardIcons": "GCPIcons: Expanded Product Card Icons",
        "GCPIconsGeneric": "GCPIcons: Generic",
        "GCPIconsHybridAndMultiCloud": "GCPIcons: Hybrid and Multi-Cloud",
        "GCPIconsMigration": "GCPIcons: Migration",
        "GCPIconsSecurity": "GCPIcons: Security",
        "GCPIconsInternetofThings": "GCPIcons: Internet of Things",
        "GCPIconsManagementTools": "GCPIcons: Management Tools",
        "GCPIconsNetworking": "GCPIcons: Networking",
        "GCPIconsOpenSourceIcons": "GCPIcons: Open Source Icons",
        "GCPIconsStorage": "GCPIcons: Storage",
    },
}

PROVIDERS = {
    "AWS4": {
        "library": "AWS4",
        "fragment_name": "aws4-shapes.generated.md",
        "sources": [{"filename": "AWS4_extracted.json", "family": "AWS4"}],
    },
    "GCP2": {
        "library": "GCP2",
        "fragment_name": "gcp-shapes.generated.md",
        "sources": [
            {
                "filename": "GCP2_extracted.json",
                "family": "GCP2",
                "start_category": "GeneralIcons",
            },
            {
                "filename": "GCPIcons_extracted.json",
                "family": "GCPIcons",
                "category_prefix": "GCPIcons",
                "suffix_overlaps_with_primary": "GCPIcons",
            },
        ],
    },
    "Azure2": {
        "library": "Azure2",
        "fragment_name": "azure-shapes.generated.md",
        "sources": [{"filename": "Azure2_extracted.json", "family": "Azure2"}],
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


def clean_name(name: str) -> str:
    return name.replace("\\n", " ").replace("\n", " ").strip()


def split_words(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip()


def display_name(library: str, category: str) -> str:
    return DISPLAY_NAMES.get(library, {}).get(category, split_words(category))


def normalize_gcpicons_name(name: str) -> str:
    name = clean_name(name)
    if " " not in name and re.search(r"[a-z][A-Z]", name):
        return split_words(name)
    return name


def require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Missing {description}: {path}")
    return path


def gcp_style(entry: dict) -> str | None:
    entry_type = entry["type"]
    if entry_type in {"stencil", "service_card", "user_device_card", "product_card_logo"}:
        return GCP_STENCIL_BASE.format(stencil=entry["stencil_name"])
    if entry_type in {"vertex_icon", "product_card"}:
        return GCP_VERTEX_ICON_BASE.format(b64=entry["base64_svg"])
    if entry_type == "edge":
        return GCP_EDGE_BASE + GCP_EDGE_SUFFIXES.get(entry["name"], "")
    if entry_type == "zone":
        fill = GCP_ZONE_FILLS.get(entry["name"], "#ffffff")
        return GCP_ZONE_BASE + f"fillColor={fill};"
    return None


def azure_style(entry: dict) -> str:
    return (
        "aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;"
        f"image={entry['image_path']};"
    )


def display_size(library: str, category: str, entry: dict) -> tuple[int, int]:
    def fallback(value: object) -> int:
        if value is None:
            return 50
        float_value = float(value)
        if float_value <= 5:
            return int(round(float_value * 100))
        return int(round(float_value))

    width = int(round(entry["width"])) if "width" in entry else fallback(entry.get("width_scale"))
    height = int(round(entry["height"])) if "height" in entry else fallback(entry.get("height_scale"))

    if library == "GCP2" and category.startswith("Icons") and max(width, height) > 100:
        return 50, 50

    return width, height


def style_for_entry(library: str, entry: dict) -> str | None:
    if library == "AWS4":
        return entry.get("style")
    if library == "Azure2":
        return azure_style(entry)
    if library == "GCP2":
        return gcp_style(entry)
    return None


def render_entry(library: str, category: str, entry: dict) -> list[str]:
    name = entry.get("render_name", entry["name"])
    lines = [f"### {name}", ""]

    if entry["type"] == "composite_template":
        lines.append("- **Type:** composite template (multi-cell)")
        lines.append("")
        return lines

    style = style_for_entry(library, entry)
    if style:
        lines.append(f"- **Style:** `{style}`")
    else:
        lines.append(f"- **Type:** `{entry['type']}`")

    width, height = display_size(library, category, entry)
    lines.append(f"- **Size:** {width}x{height}")
    lines.append("")
    return lines


def categories_from_source(source: dict, input_dir: Path) -> list[tuple[str, list[dict]]]:
    source_path = require_file(
        input_dir / source["filename"],
        "extracted JSON (run scripts/extract.py first or use --input-dir)",
    )
    data = json.loads(source_path.read_text(encoding="utf-8"))
    categories = list(data["categories"].items())
    start_category = source.get("start_category")
    if not start_category:
        return categories

    for idx, (category, _) in enumerate(categories):
        if category == start_category:
            return categories[idx:]
    return categories


def load_provider_categories(config: dict, input_dir: Path) -> list[tuple[str, list[dict]]]:
    categories: list[tuple[str, list[dict]]] = []
    primary_family = config["sources"][0]["family"]
    primary_names: set[str] = set()

    for source in config["sources"]:
        prefix = source.get("category_prefix", "")
        family = source["family"]
        suffix_family = source.get("suffix_overlaps_with_primary")
        for category, entries in categories_from_source(source, input_dir):
            adjusted_entries = []
            for entry in entries:
                clone = dict(entry)
                name = clean_name(clone["name"])
                if family == "GCPIcons":
                    name = normalize_gcpicons_name(name)
                render_name = name
                if suffix_family and name in primary_names:
                    render_name = f"{name} ({suffix_family})"
                clone["name"] = name
                clone["render_name"] = render_name
                clone["family"] = family
                adjusted_entries.append(clone)
                if family == primary_family:
                    primary_names.add(name)
            categories.append((f"{prefix}{category}", adjusted_entries))

    return categories


def dedupe_entries(library: str, categories: list[tuple[str, list[dict]]]):
    flattened = []
    total_before = 0

    for category, entries in categories:
        for entry in entries:
            total_before += 1
            width, height = display_size(library, category, entry)
            flattened.append(
                {
                    "category": category,
                    "entry": entry,
                    "area": width * height,
                    "index": len(flattened),
                    "key": (entry["family"], entry["name"]),
                }
            )

    best_by_key = {}
    for item in flattened:
        current = best_by_key.get(item["key"])
        if current is None or item["area"] < current["area"]:
            best_by_key[item["key"]] = item

    keep_indexes = {item["index"] for item in best_by_key.values()}
    removed_duplicates = total_before - len(keep_indexes)

    deduped = []
    removed_categories = 0
    for category, _ in categories:
        kept = []
        for item in flattened:
            if item["category"] == category and item["index"] in keep_indexes:
                kept.append(item["entry"])
        if kept:
            deduped.append((category, kept))
        else:
            removed_categories += 1

    return deduped, total_before, removed_duplicates, removed_categories


def build_fragment(provider_key: str, input_dir: Path) -> dict:
    config = PROVIDERS[provider_key]
    categories = load_provider_categories(config, input_dir)
    deduped, total_before, removed_duplicates, removed_categories = dedupe_entries(
        config["library"],
        categories,
    )

    final_count = sum(len(entries) for _, entries in deduped)
    lines = []
    for category, entries in deduped:
        lines.append(f"## {display_name(config['library'], category)}")
        lines.append("")
        for entry in entries:
            lines.extend(render_entry(config["library"], category, entry))

    output = "\n".join(lines).strip() + "\n"
    output = re.sub(r"\n{3,}", "\n\n", output)

    return {
        "library": config["library"],
        "fragment_name": config["fragment_name"],
        "text": output,
        "total_before": total_before,
        "removed_duplicates": removed_duplicates,
        "removed_categories": removed_categories,
        "final_count": final_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate import-ready cloud-diagram markdown fragments from extracted draw.io JSON."
    )
    parser.add_argument(
        "providers",
        nargs="*",
        help="Providers to generate: aws, gcp, azure, or all (default: all)",
    )
    parser.add_argument(
        "--input-dir",
        default=str(WORKING_ROOT),
        help="Directory containing extracted JSON files (default: drawio-shapes/working)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for generated *.generated.md fragments (default: current working directory)",
    )
    return parser.parse_args()


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


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for provider_key in normalize_provider_args(args.providers):
            stats = build_fragment(provider_key, input_dir)
            fragment_path = output_dir / stats["fragment_name"]
            fragment_path.write_text(stats["text"], encoding="utf-8")
            print(
                f"{stats['library']}: {stats['total_before']} -> {stats['final_count']} "
                f"entries, removed {stats['removed_duplicates']} duplicates, "
                f"removed {stats['removed_categories']} empty categories, "
                f"wrote {fragment_path}"
            )
    except RuntimeError as err:
        raise SystemExit(str(err))


if __name__ == "__main__":
    main()
