#!/usr/bin/env python3
"""Tests for cloud-diagram lookup and validate levers."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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
    def test_common_shapes_is_reproducible(self) -> None:
        committed = json.loads((REFERENCES / "common-shapes.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "common-shapes.json"
            generated = build(out_path=output)
            self.assertEqual(generated, committed)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                committed,
            )

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

    def test_registry_covers_eval_services(self) -> None:
        eval_services = {
            "aws": [
                "ALB",
                "EC2",
                "RDS",
                "Aurora",
                "API Gateway",
                "Lambda",
                "DynamoDB",
                "Cognito",
                "S3",
                "CloudFront",
                "Route 53",
            ],
            "azure": [
                "App Service",
                "Azure SQL",
                "Blob Storage",
                "Application Gateway",
                "VNet",
            ],
            "gcp": ["Pub/Sub", "Dataflow", "BigQuery", "Looker"],
        }
        for provider, services in eval_services.items():
            for service in services:
                with self.subTest(provider=provider, service=service):
                    self.assertIsNotNone(resolve_shape(provider, service))

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
        self.assertIn("labeled generic rounded rectangle", proc.stderr)

    def test_lookup_cli_json(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "lookup_shape.py"),
                "--provider",
                "azure",
                "--json",
                "Blob Storage",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["id"], "blob")
        self.assertIn("img/lib/azure2/storage/", result["style"])

    def test_validate_three_tier_aws(self) -> None:
        path = REFERENCES / "templates" / "three-tier-aws.drawio.xml"
        issues = collect_issues(path, "aws", ["ALB", "EC2", "RDS"])
        self.assertEqual(issues, [])

    def test_validate_three_tier_aws_resicon_matches_shape_catalog(self) -> None:
        path = REFERENCES / "templates" / "three-tier-aws.drawio.xml"
        issues = collect_issues(path, "aws", ["Internet Gateway", "NAT Gateway"])
        self.assertEqual(issues, [])

    def test_validate_three_tier_gcp(self) -> None:
        path = REFERENCES / "templates" / "three-tier-gcp.drawio.xml"
        issues = collect_issues(
            path,
            "gcp",
            ["Cloud Load Balancing", "Cloud Run", "Cloud SQL"],
        )
        self.assertEqual(issues, [])

    def test_validate_allows_nested_sibling_containment(self) -> None:
        xml = """\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="platform" value="Platform" style="fillColor=#F6F6F6;" vertex="1" parent="1">
    <mxGeometry x="0" y="0" width="400" height="300" as="geometry" />
  </mxCell>
  <mxCell id="group" value="Group" style="rounded=1;fillColor=#E1F5FE;" vertex="1" parent="1">
    <mxGeometry x="40" y="40" width="200" height="120" as="geometry" />
  </mxCell>
  <mxCell id="card" value="Service" style="rounded=1;" vertex="1" parent="1">
    <mxGeometry x="60" y="70" width="120" height="60" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "nested.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram)
        self.assertEqual(issues, [])

    def test_validate_still_flags_partial_overlap(self) -> None:
        xml = """\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="left" value="Left" style="rounded=1;" vertex="1" parent="1">
    <mxGeometry x="0" y="0" width="100" height="60" as="geometry" />
  </mxCell>
  <mxCell id="right" value="Right" style="rounded=1;" vertex="1" parent="1">
    <mxGeometry x="50" y="20" width="100" height="60" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "partial.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram)
        self.assertTrue(any("overlap: left and right" in issue for issue in issues))

    def test_validate_bad_edge(self) -> None:
        path = FIXTURES / "bad-edge.drawio"
        issues = collect_issues(path)
        self.assertTrue(any("missing mxGeometry" in issue for issue in issues))
        self.assertTrue(any("overlap" in issue for issue in issues))

    def test_validate_cli_does_not_need_drawio(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "validate_diagram.py"),
                str(FIXTURES / "bad-edge.drawio"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing mxGeometry", proc.stderr)

    def test_validate_rejects_entity_declarations(self) -> None:
        xml = """\
<!DOCTYPE mxfile [<!ENTITY repeat "unsafe">]>
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" value="&repeat;" />
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "entity.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram)
        self.assertEqual(len(issues), 1)
        self.assertIn("DTD and entity declarations are not allowed", issues[0])

    def test_validate_rejects_generic_required_service(self) -> None:
        xml = """\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="alb" value="ALB" style="rounded=1;" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="80" height="40" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "generic.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "aws", ["ALB"])
        self.assertIn("missing provider shape for ALB", issues)
        self.assertTrue(any("generic shape" in issue for issue in issues))

    def test_validate_distinguishes_gcp_service_icons(self) -> None:
        dataflow = resolve_shape("gcp", "Dataflow")
        assert dataflow is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="dataflow" value="Dataflow" style="{dataflow["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="30" height="30" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "dataflow.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "gcp", ["Pub/Sub"])
        self.assertIn("missing provider shape for Pub/Sub", issues)

    def test_validate_accepts_gcp_card_composite(self) -> None:
        pubsub = resolve_shape("gcp", "Pub/Sub")
        assert pubsub is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="pubsub-card" value="Pub/Sub" style="rounded=1;" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="160" height="70" as="geometry" />
  </mxCell>
  <mxCell id="pubsub-icon" style="{pubsub["style"]}" vertex="1" parent="pubsub-card">
    <mxGeometry x="0" y="0.5" width="30" height="30" relative="1" as="geometry">
      <mxPoint x="15" y="-15" as="offset" />
    </mxGeometry>
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "pubsub.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "gcp", ["Pub/Sub"])
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
