#!/usr/bin/env python3
"""Tests for cloud-diagram lookup and validate levers."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "skills" / "cloud-diagram" / "scripts"
REFERENCES = REPO_ROOT / "skills" / "cloud-diagram" / "references"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cloud-diagram"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_common_shapes import build  # noqa: E402
from shape_catalog import resolve_shape  # noqa: E402
from validate_diagram import collect_issues  # noqa: E402


class CloudDiagramLeversTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build()

    def test_common_shapes_built(self) -> None:
        payload = json.loads((REFERENCES / "common-shapes.json").read_text(encoding="utf-8"))
        self.assertIn("aws", payload["providers"])
        self.assertIn("alb", payload["providers"]["aws"]["services"])

    def test_lookup_alb(self) -> None:
        hit = resolve_shape("aws", "ALB")
        assert hit is not None
        self.assertIn("mxgraph.aws4", hit["style"])
        self.assertTrue(any("elastic_load_balancing" in token for token in hit["tokens"]))

    def test_lookup_s3_lambda(self) -> None:
        s3 = resolve_shape("aws", "S3")
        assert s3 is not None
        self.assertIn("resIcon=mxgraph.aws4.s3", s3["style"])
        lam = resolve_shape("aws", "Lambda")
        assert lam is not None
        self.assertIn("resIcon=mxgraph.aws4.lambda", lam["style"])

    def test_lookup_gcp_pubsub(self) -> None:
        hit = resolve_shape("gcp", "Pub/Sub")
        assert hit is not None
        self.assertEqual(hit["kind"], "gcp_card_icon")
        self.assertIn("data:image/svg+xml", hit["style"])
        self.assertEqual(hit["size"], "30x30")

    def test_lookup_azure_aks(self) -> None:
        hit = resolve_shape("azure", "AKS")
        assert hit is not None
        self.assertIn("img/lib/azure2/", hit["style"])

    def test_lookup_miss(self) -> None:
        self.assertIsNone(resolve_shape("aws", "NOSUCHTHING_XYZ"))

    def test_lookup_cli_miss_exit_code(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "lookup_shape.py"),
                "--provider",
                "aws",
                "NOSUCHTHING_XYZ",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)

    def test_validate_three_tier_aws(self) -> None:
        path = REFERENCES / "templates" / "three-tier-aws.drawio.xml"
        issues = collect_issues(path, "aws", ["ALB", "EC2", "RDS"])
        self.assertEqual(issues, [])

    def test_validate_bad_edge(self) -> None:
        path = FIXTURES / "bad-edge.drawio"
        issues = collect_issues(path)
        self.assertTrue(any("missing mxGeometry" in issue for issue in issues))
        self.assertTrue(any("overlap" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
