#!/usr/bin/env python3
"""Tests for the draw.io sidebar extractor."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACT_PATH = (
    REPO_ROOT / "plugins" / "drawio" / "skills" / "drawio-shapes" / "scripts" / "extract.py"
)
SIDEBARS = REPO_ROOT / "plugins" / "drawio" / "skills" / "drawio-shapes" / "fixtures" / "sidebars"
DRAWIO_SHAPES = REPO_ROOT / "plugins" / "drawio" / "skills" / "drawio-shapes"
PIN = "24b76c2cbd55d88e354042e8d329a2e4708972bc"

_SPEC = importlib.util.spec_from_file_location("drawio_extract", EXTRACT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
extract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(extract)


def _names(data: dict) -> list[str]:
    return [icon["name"] for icons in data["categories"].values() for icon in icons]


class DrawioExtractTest(unittest.TestCase):
    def test_gcpicons_semicolon_payload_extracts(self) -> None:
        data = extract.extract_file(SIDEBARS / "gcpicons-semicolon.js")
        self.assertEqual(data["library"], "GCPIcons")
        self.assertEqual(_names(data), ["Generic"])
        icon = data["categories"]["General"][0]
        self.assertEqual(
            icon["base64_svg"],
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==",
        )
        self.assertEqual(icon["width"], 20)
        self.assertEqual(icon["height"], 20)

    def test_gcp_sizes_honour_each_palette_s(self) -> None:
        data = extract.extract_file(SIDEBARS / "gcp2-var-s.js")
        sizes = {
            icon["name"]: (icon["width"], icon["height"])
            for icons in data["categories"].values()
            for icon in icons
        }
        self.assertEqual(
            sizes,
            {"Clock": (100, 100), "Biomedical Trio": (100, 68), "AI Hub": (38, 40)},
        )

    def test_aws_unresolved_vertex_calls_are_counted(self) -> None:
        data = extract.extract_file(SIDEBARS / "aws4-unresolved.js")
        self.assertEqual(data["library"], "AWS4")
        self.assertEqual(_names(data), ["EC2"])
        self.assertEqual(data["skipped"], 1)
        self.assertIsNone(data["skip_reason"])

    def test_aws4b_is_a_recorded_skip(self) -> None:
        data = extract.extract_file(SIDEBARS / "aws4b-skip.js")
        self.assertEqual(data["library"], "AWS4b")
        self.assertEqual(data["categories"], {})
        self.assertEqual(data["skipped"], 1)
        self.assertIn("AWS18", data["skip_reason"])

    def test_downloads_pin_commit_and_aws_stencil_file(self) -> None:
        skill = (DRAWIO_SHAPES / "SKILL.md").read_text(encoding="utf-8")
        source_map = (DRAWIO_SHAPES / "references" / "source-map.md").read_text(encoding="utf-8")
        self.assertIn(PIN, skill)
        self.assertIn(PIN, source_map)
        self.assertIn(
            PIN, (DRAWIO_SHAPES / "scripts" / "fetch_sidebar.sh").read_text(encoding="utf-8")
        )
        self.assertNotIn("?ref=dev", skill)
        self.assertNotIn("?ref=dev", source_map)
        self.assertIn("`src/main/webapp/stencils/aws4.xml`", source_map)
        self.assertNotIn("stencils/aws4/", source_map)
        for label in ("GCP3", "AWS4b", "AWS3", "AWS3D"):
            self.assertIn(label, source_map)


if __name__ == "__main__":
    unittest.main()
