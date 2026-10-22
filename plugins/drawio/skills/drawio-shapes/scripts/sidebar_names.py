#!/usr/bin/env python3
"""Allowlists for draw.io sidebar names read from a JSON request file.

Filenames that used to be interpolated into shell commands are data. The
fetch, extract, and catalog scripts read them from ``--input-file`` and
reject ``$``, backticks, quotes, newlines, and ``;``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

NAME_PATTERN = r"^[A-Za-z0-9._-]+$"
SIDEBAR_PATTERN = r"^Sidebar-[A-Za-z0-9]+\.js$"
JSON_FILENAME_PATTERN = r"^[A-Za-z0-9._-]+\.json$"
EXTRACT_FILE_PATTERN = r"^working/Sidebar-[A-Za-z0-9]+\.js$"
EXTRACT_OUTPUT_PATTERN = r"^working/[A-Za-z0-9._-]+\.json$"
RELATIVE_DIR_PATTERN = r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"

NAME_RE = re.compile(NAME_PATTERN)
SIDEBAR_RE = re.compile(SIDEBAR_PATTERN)
JSON_FILENAME_RE = re.compile(JSON_FILENAME_PATTERN)
EXTRACT_FILE_RE = re.compile(EXTRACT_FILE_PATTERN)
EXTRACT_OUTPUT_RE = re.compile(EXTRACT_OUTPUT_PATTERN)
RELATIVE_DIR_RE = re.compile(RELATIVE_DIR_PATTERN)
SHELL_META_RE = re.compile(r"[$`\"'\r\n;]")
MAX_INPUT_BYTES = 256 * 1024

_REJECTED = "no $, backticks, quotes, newlines, or ;"
_FETCH_KEYS = frozenset({"file"})


class UnsafeValueError(ValueError):
    """A filename or provider token was outside the allowlist."""


def require_name(value: object, field: str) -> str:
    """Accept a provider token or directory component."""
    if isinstance(value, str) and NAME_RE.fullmatch(value):
        return value
    raise UnsafeValueError(f"{field} must match {NAME_PATTERN} ({_REJECTED})")


def require_sidebar_filename(value: object, field: str = "file") -> str:
    """Accept one pinned sidebar basename."""
    if isinstance(value, str) and SIDEBAR_RE.fullmatch(value):
        return value
    raise UnsafeValueError(f"{field} must match {SIDEBAR_PATTERN} ({_REJECTED})")


def require_pattern(value: object, field: str, pattern: re.Pattern[str], shown: str) -> str:
    """Accept a relative path that matches ``pattern`` exactly."""
    if (
        isinstance(value, str)
        and pattern.fullmatch(value)
        and ".." not in Path(value).parts
        and SHELL_META_RE.search(value) is None
    ):
        return value
    raise UnsafeValueError(f"{field} must match {shown} ({_REJECTED})")


def reject_shell_text(value: str, field: str) -> str:
    """Reject shell metacharacters and ``..`` in a developer-supplied path.

    Absolute fixture paths used by tests stay valid. Untrusted filenames
    belong in ``--input-file``, where the stricter basename rules apply.
    """
    if SHELL_META_RE.search(value) or ".." in Path(value).parts:
        raise UnsafeValueError(f"{field} contains $, backticks, quotes, newlines, ;, or ..")
    return value


def require_keys(payload: dict[str, Any], allowed: frozenset[str]) -> None:
    """Reject unexpected JSON fields."""
    extra = sorted(set(payload) - allowed)
    if extra:
        raise UnsafeValueError(f"unknown input field(s): {', '.join(extra)}")


def _request_path(path: str) -> Path:
    if SHELL_META_RE.search(path):
        raise UnsafeValueError("--input-file contains $, backticks, quotes, newlines, or ;")
    request = Path(path)
    if not path or any(part in {"", ".", ".."} for part in request.parts):
        raise UnsafeValueError("--input-file must not contain '.', '..', or empty components")
    for part in request.parts:
        if part == "/":
            continue
        if NAME_RE.fullmatch(part) is None:
            raise UnsafeValueError(f"--input-file component must match {NAME_PATTERN}")
    if JSON_FILENAME_RE.fullmatch(request.name) is None:
        raise UnsafeValueError(f"--input-file basename must match {JSON_FILENAME_PATTERN}")
    return request


def load_json_object(path: str) -> dict[str, Any]:
    """Read one JSON object from an allowlisted request file."""
    request = _request_path(path)
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


def parse_fetch_payload(payload: dict[str, Any]) -> str:
    """Return the sidebar basename from a fetch request."""
    require_keys(payload, _FETCH_KEYS)
    return require_sidebar_filename(payload.get("file"), "file")


def main(argv: list[str] | None = None) -> int:
    """CLI used by fetch_sidebar.sh so bash never parses the JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    emit = subparsers.add_parser("emit-fetch-request")
    emit.add_argument("path")
    args = parser.parse_args(argv)
    try:
        if args.command == "emit-fetch-request":
            file_name = parse_fetch_payload(load_json_object(args.path))
            sys.stdout.write(file_name + "\n")
            return 0
    except UnsafeValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    print("ERROR: unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
