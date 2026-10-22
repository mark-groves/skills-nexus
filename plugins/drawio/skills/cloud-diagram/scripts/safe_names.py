#!/usr/bin/env python3
"""Allowlists for cloud-diagram values that must not be shell text.

Resource names, labels, categories, and filenames parsed from a user request
or from Terraform, CloudFormation, or Bicep are data. Callers write them to
a JSON file and pass that path as ``--input-file``. These checks reject
``$``, backticks, quotes, newlines, and ``;`` before a script uses the value.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NAME_PATTERN = r"^[A-Za-z0-9._-]+$"
DRAWIO_FILENAME_PATTERN = r"^[A-Za-z0-9._-]+\.drawio$"
DIAGRAM_BASENAME_PATTERN = r"^[A-Za-z0-9._-]+\.drawio(?:\.xml)?$"
JSON_FILENAME_PATTERN = r"^[A-Za-z0-9._-]+\.json$"
EXPORT_OUTPUT_PATTERN = r"^[A-Za-z0-9._-]+\.(?:svg|png|pdf)$"
SVG_FILENAME_PATTERN = r"^[A-Za-z0-9._-]+\.svg$"

NAME_RE = re.compile(NAME_PATTERN)
DRAWIO_FILENAME_RE = re.compile(DRAWIO_FILENAME_PATTERN)
DIAGRAM_BASENAME_RE = re.compile(DIAGRAM_BASENAME_PATTERN)
JSON_FILENAME_RE = re.compile(JSON_FILENAME_PATTERN)
EXPORT_OUTPUT_RE = re.compile(EXPORT_OUTPUT_PATTERN)
SVG_FILENAME_RE = re.compile(SVG_FILENAME_PATTERN)
SHELL_META_RE = re.compile(r"[$`\"'\r\n;]")
EXPORT_FORMATS = frozenset({"svg", "png", "pdf"})
MAX_INPUT_BYTES = 256 * 1024

_REJECTED = "no $, backticks, quotes, newlines, or ;"
_LOOKUP_KEYS = frozenset(
    {"provider", "query", "card", "x", "y", "label", "category", "cell_id", "json", "list"}
)
_LOOKUP_ITEM_KEYS = frozenset(
    {"provider", "query", "card", "x", "y", "label", "category", "cell_id", "list"}
)
_LOOKUP_BATCH_KEYS = frozenset({"json", "lookups"})
_VALIDATE_KEYS = frozenset({"diagram", "provider", "allow_providers", "require_services"})
_CROSSING_KEYS = frozenset({"diagram", "svg"})
_EXPORT_KEYS = frozenset({"input", "output", "format"})
_CARD_ONLY_KEYS = ("x", "y", "label", "category", "cell_id")


class UnsafeValueError(ValueError):
    """A name or filename was outside the allowlist."""


@dataclass(frozen=True)
class LookupRequest:
    """One shape lookup after allowlist checks."""

    provider: str
    query: str | None = None
    list_services: bool = False
    card: bool = False
    x: float = 200.0
    y: float = 150.0
    label: str | None = None
    category: str | None = None
    cell_id: str | None = None
    as_json: bool = False


@dataclass(frozen=True)
class ValidateRequest:
    """Diagram validation inputs after allowlist checks."""

    diagram: str
    provider: str | None
    require_services: tuple[str, ...]
    allow_providers: tuple[str, ...]


def require_name(value: object, field: str) -> str:
    """Accept a service, label, category, or other name token."""
    if isinstance(value, str) and NAME_RE.fullmatch(value):
        return value
    raise UnsafeValueError(f"{field} must match {NAME_PATTERN} ({_REJECTED})")


def require_drawio_filename(value: object, field: str) -> str:
    """Accept a diagram basename and nothing else."""
    if isinstance(value, str) and DRAWIO_FILENAME_RE.fullmatch(value):
        return value
    raise UnsafeValueError(
        f"{field} must match {DRAWIO_FILENAME_PATTERN} (basename only; {_REJECTED})"
    )


def require_svg_filename(value: object, field: str) -> str:
    """Accept an SVG basename."""
    if isinstance(value, str) and SVG_FILENAME_RE.fullmatch(value):
        return value
    raise UnsafeValueError(
        f"{field} must match {SVG_FILENAME_PATTERN} (basename only; {_REJECTED})"
    )


def require_export_output(value: object, field: str) -> str:
    """Accept an svg, png, or pdf basename."""
    if isinstance(value, str) and EXPORT_OUTPUT_RE.fullmatch(value):
        return value
    raise UnsafeValueError(
        f"{field} must match {EXPORT_OUTPUT_PATTERN} (basename only; {_REJECTED})"
    )


def require_developer_path(value: str, field: str, basename_re: re.Pattern[str]) -> Path:
    """Accept a local fixture path whose every component is an allowlisted name.

    Untrusted names from a request or from IaC must use ``--input-file``
    instead of this positional form. ``..``, shell metacharacters, and a
    basename outside ``basename_re`` are rejected either way.
    """
    if SHELL_META_RE.search(value):
        raise UnsafeValueError(f"{field} contains $, backticks, quotes, newlines, or ;")
    path = Path(value)
    if not value or any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafeValueError(f"{field} must not contain '.', '..', or empty components")
    for part in path.parts:
        if part == "/":
            continue
        if NAME_RE.fullmatch(part) is None:
            raise UnsafeValueError(f"{field} component must match {NAME_PATTERN} ({_REJECTED})")
    if basename_re.fullmatch(path.name) is None:
        raise UnsafeValueError(f"{field} basename must match {basename_re.pattern} ({_REJECTED})")
    return path


def require_provider(value: object, providers: frozenset[str], field: str = "provider") -> str:
    """Accept a provider id from the known set."""
    name = require_name(value, field)
    if name not in providers:
        allowed = ", ".join(sorted(providers))
        raise UnsafeValueError(f"{field} must be one of: {allowed}")
    return name


def require_bool(value: object, field: str) -> bool:
    """Accept a JSON boolean. Integers are not booleans."""
    if isinstance(value, bool):
        return value
    raise UnsafeValueError(f"{field} must be a boolean")


def require_finite_number(value: object, field: str) -> float:
    """Accept a finite JSON number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UnsafeValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise UnsafeValueError(f"{field} must be a finite number")
    return number


def require_name_list(value: object, field: str) -> tuple[str, ...]:
    """Accept a JSON array of allowlisted names."""
    if not isinstance(value, list):
        raise UnsafeValueError(f"{field} must be an array of names matching {NAME_PATTERN}")
    return tuple(require_name(item, field) for item in value)


def split_csv_names(value: str, field: str) -> list[str]:
    """Split a comma-separated argv list and allowlist each token."""
    names: list[str] = []
    for part in value.split(","):
        item = part.strip()
        if item:
            names.append(require_name(item, field))
    return names


def require_keys(payload: dict[str, Any], allowed: frozenset[str]) -> None:
    """Reject unexpected JSON fields so typos cannot skip a check."""
    extra = sorted(set(payload) - allowed)
    if extra:
        raise UnsafeValueError(f"unknown input field(s): {', '.join(extra)}")


def load_json_object(path: str) -> dict[str, Any]:
    """Read one JSON object from a request file or from stdin (``-``)."""
    if path == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    else:
        request = require_developer_path(path, "--input-file", JSON_FILENAME_RE)
        if not request.is_file():
            raise UnsafeValueError(f"--input-file not found: {request.name}")
        raw = request.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise UnsafeValueError("input file exceeds 256 KiB")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise UnsafeValueError(f"input file is not UTF-8 JSON: {err}") from err
    if not isinstance(payload, dict):
        raise UnsafeValueError("input file must be a JSON object")
    return payload


def _optional_name(item: dict[str, Any], key: str) -> str | None:
    if key not in item:
        return None
    return require_name(item[key], key)


def _parse_lookup_item(
    item: object,
    providers: frozenset[str],
    *,
    inherited_json: bool | None,
) -> LookupRequest:
    if not isinstance(item, dict):
        raise UnsafeValueError("lookup must be a JSON object")
    allowed = _LOOKUP_ITEM_KEYS if inherited_json is not None else _LOOKUP_KEYS
    require_keys(item, allowed)
    if "provider" not in item:
        raise UnsafeValueError("provider is required")
    provider = require_provider(item["provider"], providers)
    listing = require_bool(item["list"], "list") if "list" in item else False
    card = require_bool(item["card"], "card") if "card" in item else False
    if inherited_json is None:
        as_json = require_bool(item["json"], "json") if "json" in item else False
    else:
        as_json = inherited_json
    if listing and card:
        raise UnsafeValueError("list and card cannot both be set")
    if listing and "query" in item:
        raise UnsafeValueError("list does not take a query")
    if listing and as_json:
        raise UnsafeValueError("list and json cannot both be set")
    if not listing and "query" not in item:
        raise UnsafeValueError("query is required unless list is true")
    extras = [key for key in _CARD_ONLY_KEYS if key in item]
    if extras and not card:
        raise UnsafeValueError("x, y, label, category, and cell_id require card=true")
    if card and provider != "gcp":
        raise UnsafeValueError("card is only supported for provider gcp")
    query = None if listing else require_name(item["query"], "query")
    return LookupRequest(
        provider=provider,
        query=query,
        list_services=listing,
        card=card,
        x=require_finite_number(item["x"], "x") if "x" in item else 200.0,
        y=require_finite_number(item["y"], "y") if "y" in item else 150.0,
        label=_optional_name(item, "label"),
        category=_optional_name(item, "category"),
        cell_id=_optional_name(item, "cell_id"),
        as_json=as_json,
    )


def parse_lookup_payload(payload: dict[str, Any], providers: frozenset[str]) -> list[LookupRequest]:
    """Parse one lookup or a ``lookups`` array from a request file."""
    if "lookups" in payload:
        require_keys(payload, _LOOKUP_BATCH_KEYS)
        as_json = require_bool(payload["json"], "json") if "json" in payload else False
        lookups = payload["lookups"]
        if not isinstance(lookups, list) or not lookups:
            raise UnsafeValueError("lookups must be a non-empty array")
        return [_parse_lookup_item(item, providers, inherited_json=as_json) for item in lookups]
    require_keys(payload, _LOOKUP_KEYS)
    return [_parse_lookup_item(payload, providers, inherited_json=None)]


def parse_validate_payload(payload: dict[str, Any], providers: frozenset[str]) -> ValidateRequest:
    """Parse a diagram validation request. ``diagram`` is a basename."""
    require_keys(payload, _VALIDATE_KEYS)
    if "diagram" not in payload:
        raise UnsafeValueError("diagram is required")
    provider = None
    if "provider" in payload and payload["provider"] is not None:
        provider = require_provider(payload["provider"], providers)
    return ValidateRequest(
        diagram=require_drawio_filename(payload["diagram"], "diagram"),
        provider=provider,
        require_services=require_name_list(payload.get("require_services", []), "require_services"),
        allow_providers=require_name_list(payload.get("allow_providers", []), "allow_providers"),
    )


def parse_crossings_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """Parse diagram and SVG basenames for the crossing check."""
    require_keys(payload, _CROSSING_KEYS)
    return (
        require_drawio_filename(payload.get("diagram"), "diagram"),
        require_svg_filename(payload.get("svg"), "svg"),
    )


def parse_export_payload(payload: dict[str, Any]) -> tuple[str, str, str]:
    """Parse export basenames and the svg, png, or pdf format."""
    require_keys(payload, _EXPORT_KEYS)
    if "input" not in payload or "output" not in payload:
        raise UnsafeValueError("export request needs input and output")
    source = require_drawio_filename(payload["input"], "input")
    output = require_export_output(payload["output"], "output")
    suffix = output.rsplit(".", 1)[-1]
    if "format" in payload:
        fmt = payload["format"]
        if not isinstance(fmt, str) or fmt not in EXPORT_FORMATS:
            raise UnsafeValueError("format must be svg, png, or pdf")
        if fmt != suffix:
            raise UnsafeValueError("format does not match the output filename")
    else:
        fmt = suffix
    return source, output, fmt


def check_export_argv(source: str, output: str, fmt: str) -> None:
    """Allowlist positional export paths used by local fixtures."""
    if fmt not in EXPORT_FORMATS:
        raise UnsafeValueError("format must be svg, png, or pdf")
    require_developer_path(source, "input", DIAGRAM_BASENAME_RE)
    exported = require_developer_path(output, "output", EXPORT_OUTPUT_RE)
    if exported.suffix.lstrip(".") != fmt:
        raise UnsafeValueError("format does not match the output filename")


def _emit_export_request(path: str) -> None:
    source, output, fmt = parse_export_payload(load_json_object(path))
    sys.stdout.write(f"{source}\n{output}\n{fmt}\n")


def main(argv: list[str] | None = None) -> int:
    """CLI used by export_diagram.sh so bash never parses the JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    emit = subparsers.add_parser("emit-export-request")
    emit.add_argument("path")
    check = subparsers.add_parser("check-export-argv")
    check.add_argument("--input", required=True)
    check.add_argument("--output", required=True)
    check.add_argument("--format", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "emit-export-request":
            _emit_export_request(args.path)
            return 0
        if args.command == "check-export-argv":
            check_export_argv(args.input, args.output, args.format)
            return 0
    except UnsafeValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    print("ERROR: unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
