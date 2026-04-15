#!/usr/bin/env python3
"""Extract shape definitions from draw.io sidebar JS files.

Usage:
    python extract.py <sidebar_js_file> [--output <path>]

Supports GCPIcons, GCP2, and other draw.io sidebar files.
Outputs structured JSON with all extracted shapes grouped by category.
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path

KNOWN_LIBRARIES = {"GCPIcons", "GCP2", "AWS4", "Azure2"}
BASE64_SVG_PREFIX = r"(?:PHN2Zy|PD94bWw)"
PALETTE_PREFIX_RE = re.compile(
    r"Sidebar\.prototype\.add(\w+)Palette\s*=\s*function\([^)]*\)\s*\{"
)
AZURE_PALETTE_CALL_RE = re.compile(
    r"this\.addAzure2(\w+)Palette\([^;]*?\b[A-Za-z_]\w*\s*\+ '([^']+/)'\);",
    re.S,
)
AZURE_BASE_SIZE_RE = re.compile(
    r"Sidebar\.prototype\.addAzure2Palette\s*=\s*function\([^)]*\)\s*\{"
    r".*?\bvar r = (\d+);",
    re.S,
)
AZURE_DIM_EXPR = r"(?:[A-Za-z_]\w*\s*\*\s*[\d.]+|[\d.]+)"
AZURE_SVG_VAR_RE = re.compile(
    r"this\.createVertexTemplateEntry\(\s*[A-Za-z_]\w*\s*\+ '([^']+\.svg);',\s*"
    rf"({AZURE_DIM_EXPR}),\s*({AZURE_DIM_EXPR}),\s*'[^']*',\s*'([^']+)'",
    re.S,
)
AZURE_SVG_INLINE_RE = re.compile(
    r"this\.createVertexTemplateEntry\(\s*'[^']*image="
    r"(img/lib/azure2/[^']+\.svg);',\s*"
    rf"({AZURE_DIM_EXPR}),\s*({AZURE_DIM_EXPR}),\s*'[^']*',\s*'([^']+)'",
    re.S,
)
AWS_STYLE_EXPR = r"(?:'[^']*'|[A-Za-z_]\w*|mxConstants\.STYLE_SHAPE|\+|\s)+?"
AWS_DIM_EXPR = r"(?:[A-Za-z_]\w*(?:\s*\*\s*[\d.]+)?|[\d.]+)"
AWS_STYLE_ENTRY_RE = re.compile(
    r"this\.createVertexTemplateEntry\(\s*"
    rf"({AWS_STYLE_EXPR})\s*,\s*"
    rf"({AWS_DIM_EXPR}),\s*({AWS_DIM_EXPR}),\s*"
    r"'[^']*',\s*'([^']+)'",
    re.S,
)
STRING_VAR_RE = re.compile(r"^\s*var\s+([A-Za-z_]\w*)\s*=\s*(.+?);\s*$", re.M)


# ---------------------------------------------------------------------------
# Pattern library — regex patterns for each shape encoding format
# ---------------------------------------------------------------------------


def _compile_patterns(lib_prefix):
    """Build regex patterns parameterised by library prefix (e.g. 'GCP2')."""
    return {
        # Base64 SVG concatenated via variable: (n|s1) + 'BASE64;'
        "var_b64": re.compile(
            rf"this\.createVertexTemplateEntry\(\s*(?:n|s1) \+ '({BASE64_SVG_PREFIX}[A-Za-z0-9+/=]+)',\s*"
            r"s \* ([\d.]+),\s*s \* ([\d.]+),\s*'[^']*',\s*'([^']+)'"
        ),
        # Base64 SVG with image= prefix via variable: n + 'image=data:...,BASE64;'
        "var_image_b64": re.compile(
            r"this\.createVertexTemplateEntry\("
            rf"n \+ 'image=data:image/svg\+xml,({BASE64_SVG_PREFIX}[A-Za-z0-9+/=]+);',\s*"
            r"s \* ([\d.]+),\s*s \* ([\d.]+),\s*'([^']*)'"
        ),
        # Inline full style with base64 SVG
        "inline_b64": re.compile(
            r"this\.createVertexTemplateEntry\(\s*"
            r"'[^']*image=data:image/svg\+xml,"
            rf"({BASE64_SVG_PREFIX}[A-Za-z0-9+/=]+);',\s*"
            r"s \* ([\d.]+),\s*s \* ([\d.]+),\s*'[^']*',\s*'([^']+)'"
        ),
        # Inline editableCssRules style with base64 SVG (GCPIcons Generic etc.)
        "inline_editable_b64": re.compile(
            r"this\.createVertexTemplateEntry\(\s*"
            r"'editableCssRules=[^,]+,"
            rf"({BASE64_SVG_PREFIX}[A-Za-z0-9+/=]+);',\s*"
            r"s \* ([\d.]+),\s*s \* ([\d.]+),\s*'[^']*',\s*'([^']+)'"
        ),
        # Stencil reference via variable: n + 'stencil_name'
        "var_stencil": re.compile(
            r"this\.createVertexTemplateEntry\(n \+ '(\w+)',\s*"
            r"s \* ([\d.]+),\s*s \* ([\d.]+),\s*null,\s*'([^']+)'"
        ),
        # Stencil reference inlined in full style string
        "inline_stencil": re.compile(
            r"this\.createVertexTemplateEntry\("
            r"'([^']+shape=(?:mxgraph\.\w+\.\w+|ellipse)[^']*)',\s*"
            r"s \* ([\d.]+),\s*s \* ([\d.]+),\s*null,\s*'([^']+)'"
        ),
        # Product card set with base64 icon variable
        "product_card": re.compile(
            rf"icon = '([A-Za-z0-9+/=]+);';\s*"
            rf"this\.add{lib_prefix}UserProductCardSet\('([^']+)'"
        ),
        # Service card: this.addXServiceCard('Name', 'stencil', w, h, ...)
        "service_card": re.compile(
            rf"this\.add{lib_prefix}ServiceCard\("
            r"'([^']+)',\s*'([^']+)',\s*([\d.]+),\s*([\d.]+)"
        ),
        # User device card
        "user_device_card": re.compile(
            rf"this\.add{lib_prefix}UserDeviceCard\('([^']+)',\s*'([^']+)'"
        ),
        # Product card set (logo-based stencil)
        "product_card_logo": re.compile(
            rf"this\.add{lib_prefix}ProductCardSet\('([^']+)',\s*'([^']+)'"
        ),
        # Edge templates
        "edge": re.compile(
            r"this\.createEdgeTemplateEntry\([^,]+,\s*\d+,\s*\d+,"
            r"\s*'[^']*',\s*'([^']+)'"
        ),
        # Composite multi-cell templates
        "composite": re.compile(
            r"createVertexTemplateFromCells\(\[[^\]]+\][^)]*,"
            r"\s*'([^']+)'\s*\)"
        ),
        # Zone containers: s + 'fillColor=...'
        "zone_var": re.compile(
            r"this\.createVertexTemplateEntry\(s \+ '([^']+)',\s*"
            r"(\d+),\s*(\d+),\s*'[^']*',\s*'([^']+)'"
        ),
        # Zone containers: inline fillColor/strokeColor style
        "zone_inline": re.compile(
            r"this\.createVertexTemplateEntry\("
            r"'((?:fillColor|strokeColor)=[^']+)',\s*"
            r"(\d+),\s*(\d+),\s*'[^']*',\s*'([^']+)'"
        ),
    }


# ---------------------------------------------------------------------------
# Extraction logic
# ---------------------------------------------------------------------------


def detect_library(content):
    """Detect the library type from the sidebar JS content."""
    if "addGCPIconsPalette" in content:
        return "GCPIcons"
    if "addGCP2Palette" in content:
        return "GCP2"
    if "addAWS4Palette" in content or "addAWS4" in content:
        return "AWS4"
    if "addAzure2Palette" in content or "addAzure2" in content:
        return "Azure2"
    return "Unknown"


def find_palette_prefix(content):
    """Find the palette function prefix (e.g. 'GCPIcons', 'GCP2')."""
    # Look for the top-level addXPalette function that registers all sub-palettes.
    m = PALETTE_PREFIX_RE.search(content)
    return m.group(1) if m else "Unknown"


def split_by_palette(content, prefix):
    """Split content into sections by palette function definitions."""
    pattern = (
        rf"Sidebar\.prototype\.add{prefix}(\w+)Palette\s*=\s*function\([^)]*\)"
    )
    return re.split(pattern, content)


def extract_categories(content, prefix):
    """Get deduplicated list of category names."""
    cats = re.findall(rf"this\.add{prefix}(\w+)Palette\b", content)
    seen = set()
    result = []
    for c in cats:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def clean_name(name):
    """Normalize labels captured from sidebar JS calls."""
    return name.replace("\\n", " ").replace("\n", " ").strip()


def _split_concat_expression(expr):
    """Split a JS string concatenation expression on + outside quotes."""
    parts = []
    current = []
    quote_char = None

    for ch in expr:
        if ch in {"'", '"'}:
            if quote_char is None:
                quote_char = ch
            elif quote_char == ch:
                quote_char = None
            current.append(ch)
        elif ch == "+" and quote_char is None:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(ch)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)

    return parts


def resolve_string_expression(expr, variables):
    """Resolve a limited JS string concatenation expression to a concrete string."""
    resolved = []

    for token in _split_concat_expression(expr):
        if (
            (token.startswith("'") and token.endswith("'"))
            or (token.startswith('"') and token.endswith('"'))
        ):
            resolved.append(token[1:-1])
        elif token == "mxConstants.STYLE_SHAPE":
            resolved.append("shape")
        elif token in variables:
            resolved.append(variables[token])
        else:
            return None

    return "".join(resolved)


def extract_string_variables(section, initial_vars=None):
    """Resolve simple string variable declarations inside a palette section."""
    variables = dict(initial_vars or {})
    pending = {
        match.group(1): match.group(2)
        for match in STRING_VAR_RE.finditer(section)
    }

    progress = True
    while pending and progress:
        progress = False
        for name, expr in list(pending.items()):
            value = resolve_string_expression(expr, variables)
            if value is None:
                continue
            variables[name] = value
            del pending[name]
            progress = True

    return variables


def parse_dimension(expr, base_size=None, numeric_vars=None):
    """Parse a numeric dimension expression into scale and pixel values."""
    expr = " ".join(expr.split())
    numeric_vars = numeric_vars or {}

    scale_match = re.fullmatch(r"[A-Za-z_]\w*\s*\*\s*([\d.]+)", expr)
    if scale_match:
        var_name = re.match(r"([A-Za-z_]\w*)", expr).group(1)
        scale = float(scale_match.group(1))
        if var_name in numeric_vars:
            return None, int(round(numeric_vars[var_name] * scale))
        value = int(round(base_size * scale)) if base_size is not None else None
        return scale, value

    var_match = re.fullmatch(r"([A-Za-z_]\w*)", expr)
    if var_match and var_match.group(1) in numeric_vars:
        return None, int(round(numeric_vars[var_match.group(1)]))

    numeric_match = re.fullmatch(r"[\d.]+", expr)
    if numeric_match:
        value = int(round(float(expr)))
        return None, value

    raise ValueError(f"Unsupported dimension expression: {expr}")


def build_dimension_fields(width_expr, height_expr, base_size=None, numeric_vars=None):
    """Build consistent JSON fields for width/height expressions."""
    width_scale, width = parse_dimension(width_expr, base_size, numeric_vars)
    height_scale, height = parse_dimension(height_expr, base_size, numeric_vars)

    fields = {}
    if width_scale is not None:
        fields["width_scale"] = width_scale
    if height_scale is not None:
        fields["height_scale"] = height_scale
    if width is not None:
        fields["width"] = width
    if height is not None:
        fields["height"] = height

    return fields


def extract_azure_context(content):
    """Extract Azure palette folder mappings and base size."""
    base_size_match = AZURE_BASE_SIZE_RE.search(content)
    base_size = int(base_size_match.group(1)) if base_size_match else None

    palette_paths = {}
    for match in AZURE_PALETTE_CALL_RE.finditer(content):
        category, folder = match.groups()
        palette_paths[category] = f"img/lib/azure2/{folder}"

    return {"base_size": base_size, "palette_paths": palette_paths}


def extract_azure_section(section, category_name, azure_context):
    """Extract Azure2 SVG image-path entries from a single palette section."""
    icons = []
    category_prefix = azure_context["palette_paths"].get(category_name)
    base_size = azure_context["base_size"]

    for match in AZURE_SVG_VAR_RE.finditer(section):
        filename, width_expr, height_expr, name = match.groups()
        if not category_prefix:
            raise RuntimeError(
                f"Missing Azure folder prefix for palette '{category_name}'"
            )

        icons.append(
            {
                "name": clean_name(name),
                "type": "svg_image",
                "image_path": f"{category_prefix}{filename}",
                **build_dimension_fields(width_expr, height_expr, base_size),
            }
        )

    for match in AZURE_SVG_INLINE_RE.finditer(section):
        image_path, width_expr, height_expr, name = match.groups()
        icons.append(
            {
                "name": clean_name(name),
                "type": "svg_image",
                "image_path": image_path,
                **build_dimension_fields(width_expr, height_expr, base_size),
            }
        )

    return icons


def extract_aws_section(section, stencil_namespace):
    """Extract AWS4 entries with resolved full style strings."""
    icons = []
    style_vars = extract_string_variables(section, {"gn": stencil_namespace})
    numeric_vars = {"s": 1, "w": 100, "h": 100, "w2": 78}

    for match in AWS_STYLE_ENTRY_RE.finditer(section):
        style_expr, width_expr, height_expr, name = match.groups()
        style = resolve_string_expression(style_expr, style_vars)
        if style is None:
            continue

        entry = {
            "name": clean_name(name),
            "type": "stencil",
            "style": style,
            **build_dimension_fields(
                width_expr,
                height_expr,
                numeric_vars=numeric_vars,
            ),
        }

        res_icon_match = re.search(r"resIcon=([\w.]+)", style)
        shape_match = re.search(r"shape=([\w.]+)", style)
        if res_icon_match:
            entry["stencil_name"] = res_icon_match.group(1)
        elif shape_match:
            entry["stencil_name"] = shape_match.group(1)

        icons.append(entry)

    return icons


def extract_section(section, patterns, stencil_namespace):
    """Extract all shapes from a single palette section."""
    icons = []
    seen_names = set()
    base_icon_size = 100

    def _add(entry):
        icons.append(entry)

    # Base64 SVG via variable
    for m in patterns["var_b64"].finditer(section):
        b64, w, h, name = m.groups()
        _add(
            {
                "name": name,
                "type": "vertex_icon",
                "base64_svg": b64.rstrip(";"),
                **build_dimension_fields(w, h, base_size=base_icon_size),
            }
        )

    # Base64 SVG with image= prefix via variable
    for m in patterns["var_image_b64"].finditer(section):
        b64, w, h, name = m.groups()
        _add(
            {
                "name": name,
                "type": "vertex_icon",
                "base64_svg": b64,
                **build_dimension_fields(w, h, base_size=base_icon_size),
            }
        )

    # Inline base64 SVG
    for m in patterns["inline_b64"].finditer(section):
        b64, w, h, name = m.groups()
        _add(
            {
                "name": name,
                "type": "vertex_icon",
                "base64_svg": b64,
                **build_dimension_fields(w, h, base_size=base_icon_size),
            }
        )

    # Inline editableCssRules base64 SVG
    for m in patterns["inline_editable_b64"].finditer(section):
        b64, w, h, name = m.groups()
        _add(
            {
                "name": name,
                "type": "vertex_icon",
                "base64_svg": b64,
                **build_dimension_fields(w, h, base_size=base_icon_size),
            }
        )

    # Stencil reference via variable
    for m in patterns["var_stencil"].finditer(section):
        stencil, w, h, name = m.groups()
        _add(
            {
                "name": name,
                "type": "stencil",
                "stencil_name": f"{stencil_namespace}.{stencil}",
                **build_dimension_fields(w, h, base_size=base_icon_size),
            }
        )

    # Stencil reference inlined
    for m in patterns["inline_stencil"].finditer(section):
        style, w, h, name = m.groups()
        shape_m = re.search(r"shape=([\w.]+)", style)
        shape = shape_m.group(1) if shape_m else "unknown"
        _add(
            {
                "name": name,
                "type": "stencil",
                "stencil_name": shape,
                **build_dimension_fields(w, h, base_size=base_icon_size),
            }
        )

    # Product card sets with base64 icon
    for m in patterns["product_card"].finditer(section):
        b64, name = m.groups()
        _add(
            {
                "name": clean_name(name),
                "type": "product_card",
                "base64_svg": b64,
            }
        )

    # Service cards
    for m in patterns["service_card"].finditer(section):
        name, stencil, w, h = m.groups()
        _add(
            {
                "name": clean_name(name),
                "type": "service_card",
                "stencil_name": f"{stencil_namespace}.{stencil}",
                "width": float(w),
                "height": float(h),
            }
        )

    # User device cards
    for m in patterns["user_device_card"].finditer(section):
        name, stencil = m.groups()
        _add(
            {
                "name": name,
                "type": "user_device_card",
                "stencil_name": f"{stencil_namespace}.{stencil}",
            }
        )

    # Product card sets (logo-based)
    for m in patterns["product_card_logo"].finditer(section):
        name, stencil = m.groups()
        _add(
            {
                "name": clean_name(name),
                "type": "product_card_logo",
                "stencil_name": f"{stencil_namespace}.{stencil}",
            }
        )

    # Edge templates
    for m in patterns["edge"].finditer(section):
        _add({"name": m.group(1), "type": "edge"})

    # Composite multi-cell templates (deduped)
    for m in patterns["composite"].finditer(section):
        name = m.group(1)
        if name not in seen_names:
            seen_names.add(name)
            _add({"name": name, "type": "composite_template"})

    # Zone containers (variable style)
    for m in patterns["zone_var"].finditer(section):
        _, w, h, name = m.groups()
        if not any(ic["name"] == name for ic in icons):
            _add({"name": name, "type": "zone", "width": int(w), "height": int(h)})

    # Zone containers (inline style)
    for m in patterns["zone_inline"].finditer(section):
        _, w, h, name = m.groups()
        if not any(ic["name"] == name for ic in icons):
            _add({"name": name, "type": "zone", "width": int(w), "height": int(h)})

    return icons


def extract_file(filepath):
    """Extract all shapes from a draw.io sidebar JS file."""
    content = Path(filepath).read_text()
    lib = detect_library(content)
    prefix = find_palette_prefix(content)

    # Determine stencil namespace
    ns_map = {
        "GCPIcons": "mxgraph.gcpicons",
        "GCP2": "mxgraph.gcp2",
        "AWS4": "mxgraph.aws4",
        "Azure2": "mxgraph.azure2",
    }
    stencil_ns = ns_map.get(lib, f"mxgraph.{lib.lower()}")

    print(f"Library: {lib}")
    print(f"Palette prefix: {prefix}")
    print(f"Stencil namespace: {stencil_ns}")

    categories = extract_categories(content, prefix)
    print(f"Categories: {len(categories)}")

    sections = split_by_palette(content, prefix)
    patterns = _compile_patterns(prefix)
    azure_context = extract_azure_context(content) if lib == "Azure2" else None

    result = {}
    for i in range(1, len(sections), 2):
        cat_name = sections[i]
        section = sections[i + 1]
        if lib == "Azure2":
            icons = extract_azure_section(section, cat_name, azure_context)
        elif lib == "AWS4":
            icons = extract_aws_section(section, stencil_ns)
        else:
            icons = extract_section(section, patterns, stencil_ns)
        result[cat_name] = icons

    return {
        "source": f"jgraph/drawio {Path(filepath).name}",
        "library": lib,
        "stencil_namespace": stencil_ns,
        "categories": result,
    }


def verify_base64(data):
    """Verify all base64 SVGs decode without error."""
    errors = 0
    for cat, icons in data["categories"].items():
        for icon in icons:
            if "base64_svg" in icon:
                try:
                    base64.b64decode(icon["base64_svg"])
                except Exception as e:
                    print(f"  WARNING: {cat}/{icon['name']}: {e}")
                    errors += 1
    return errors


def print_summary(data):
    """Print a human-readable summary of extracted shapes."""
    total = 0
    for cat, icons in data["categories"].items():
        count = len(icons)
        total += count
        print(f"\n  {cat} ({count} entries):")
        for icon in icons:
            t = icon["type"]
            print(f"    [{t:22}] {icon['name']}")

    cat_count = len(data["categories"])
    print(f"\n=== Total: {total} entries across {cat_count} categories ===")
    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Extract shapes from a draw.io sidebar JS file."
    )
    parser.add_argument("file", help="Path to the sidebar JS file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path (default: <file>_extracted.json)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress per-icon output, show summary only",
    )
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: {filepath} not found", file=sys.stderr)
        sys.exit(1)

    data = extract_file(filepath)

    if not args.quiet:
        print_summary(data)

    total = sum(len(icons) for icons in data["categories"].values())
    if data["library"] in KNOWN_LIBRARIES and total == 0:
        print(
            (
                f"Error: extracted 0 entries from known library "
                f"{data['library']}. The upstream file format likely changed."
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    errors = verify_base64(data)
    if errors == 0:
        print("All base64 SVGs decode successfully.")
    else:
        print(f"{errors} base64 decode error(s) found.")

    output_path = args.output or filepath.with_suffix("").name + "_extracted.json"
    Path(output_path).write_text(json.dumps(data, indent=2))
    print(f"\nSaved to {output_path} ({total} entries)")


if __name__ == "__main__":
    main()
