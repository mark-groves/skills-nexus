#!/usr/bin/env python3
"""Tests for the edge-through-icon check on official draw.io SVG exports.

SVG fixtures come from tests/fixtures/cloud-diagram/edges/refresh.py:
draw.io 31.7.0 exports with embedded image data removed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "plugins" / "drawio" / "skills" / "cloud-diagram" / "scripts"
TEMPLATES = REPO_ROOT / "plugins" / "drawio" / "skills" / "cloud-diagram" / "references" / "templates"
EDGES = Path(__file__).resolve().parent / "fixtures" / "cloud-diagram" / "edges"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_edge_crossings import find_crossings  # noqa: E402


def pairs(drawio: Path, svg: Path) -> set[tuple[str, str]]:
    return {(hit.edge, hit.icon) for hit in find_crossings(drawio, svg)}


class EdgeCrossingTest(unittest.TestCase):
    def test_azure_starter_before_fix_routes_users_through_two_icons(self) -> None:
        self.assertEqual(
            pairs(EDGES / "azure-before.drawio", EDGES / "azure-before.svg"),
            {("edge-users-appgw", "app-svc"), ("edge-users-appgw", "sql")},
        )

    def test_gcp_starter_before_fix_routes_users_through_two_cards(self) -> None:
        self.assertEqual(
            pairs(EDGES / "gcp-before.drawio", EDGES / "gcp-before.svg"),
            {("edge-users-lb", "card-run"), ("edge-users-lb", "card-sql")},
        )

    def test_starter_exports_match_the_committed_starters(self) -> None:
        digests = json.loads((EDGES / "starter-exports.json").read_text(encoding="utf-8"))
        for name, digest in digests.items():
            with self.subTest(name=name):
                starter = TEMPLATES / f"{name}.drawio.xml"
                self.assertEqual(
                    hashlib.sha256(starter.read_bytes()).hexdigest(),
                    digest,
                    f"{name} changed; re-export with tests/fixtures/cloud-diagram/edges/refresh.py",
                )

    def test_starters_route_no_edge_through_an_icon(self) -> None:
        for name in ("three-tier-aws", "three-tier-azure", "three-tier-gcp"):
            with self.subTest(name=name):
                self.assertEqual(
                    pairs(TEMPLATES / f"{name}.drawio.xml", EDGES / f"{name}.svg"),
                    set(),
                )

    def test_small_glyphs_centred_on_an_edge_are_annotations(self) -> None:
        # Grey encrypted-data glyphs drawn on each encrypted link.
        self.assertEqual(
            pairs(EDGES / "aws-encrypted-glyphs.drawio", EDGES / "aws-encrypted-glyphs.svg"),
            set(),
        )
        # Numbered step badges drawn on each flow.
        self.assertEqual(
            pairs(EDGES / "gcp-step-badges.drawio", EDGES / "gcp-step-badges.svg"),
            set(),
        )

    def test_unattached_edge_end_may_point_into_a_card(self) -> None:
        self.assertEqual(
            pairs(EDGES / "gcp-dangling-pointer.drawio", EDGES / "gcp-dangling-pointer.svg"),
            set(),
        )

    def test_cli_names_each_crossing_and_fails(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "check_edge_crossings.py"),
                str(EDGES / "azure-before.drawio"),
                str(EDGES / "azure-before.svg"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(
            "edge edge-users-appgw (Users -> Application Gateway) passes through "
            "icon sql (Azure SQL Database)",
            result.stdout,
        )
        self.assertIn("passes through icon app-svc (App Service)", result.stdout)

    def test_cli_passes_a_clean_export(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "check_edge_crossings.py"),
                str(TEMPLATES / "three-tier-aws.drawio.xml"),
                str(EDGES / "three-tier-aws.svg"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_cli_refuses_an_svg_without_draw_io_cell_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "headless.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 L 9 9" fill="none"/></svg>',
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "check_edge_crossings.py"),
                    str(EDGES / "azure-before.drawio"),
                    str(svg),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("export_diagram.sh", result.stderr)


if __name__ == "__main__":
    unittest.main()
