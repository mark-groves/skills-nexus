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
SCRIPTS = (
    REPO_ROOT / "plugins" / "drawio" / "skills" / "cloud-diagram" / "scripts"
)
REFERENCES = (
    REPO_ROOT / "plugins" / "drawio" / "skills" / "cloud-diagram" / "references"
)
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cloud-diagram"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_common_shapes import build  # noqa: E402
from gcp_card import emit_gcp_service_card  # noqa: E402
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
        self.assertIn("fillColor=#8C4FFF", hit["style"])

    def test_lookup_aws_groups_prefer_containers(self) -> None:
        for query, token, size in (
            ("VPC", "grIcon=mxgraph.aws4.group_vpc2", "700x500"),
            (
                "Availability Zone",
                "grIcon=mxgraph.aws4.group_availability_zone",
                "300x450",
            ),
            ("Account", "grIcon=mxgraph.aws4.group_account", "820x620"),
        ):
            with self.subTest(query=query):
                hit = resolve_shape("aws", query)
                assert hit is not None
                self.assertEqual(hit["kind"], "group")
                self.assertIn(token, hit["style"])
                self.assertIn("container=1", hit["style"])
                self.assertEqual(hit["size"], size)
                self.assertEqual(hit["tokens"], [token])

    def test_lookup_azure_subnet_prefers_swimlane(self) -> None:
        hit = resolve_shape("azure", "Subnet")
        assert hit is not None
        self.assertEqual(hit["kind"], "group")
        self.assertTrue(hit["style"].startswith("swimlane;"))
        self.assertIn("container=1", hit["style"])
        self.assertEqual(hit["size"], "400x250")
        self.assertNotIn("img/lib/azure2/networking/Subnet.svg", hit["style"])
        self.assertTrue(hit["tokens"])
        self.assertTrue(all(token.startswith("azure.group:") for token in hit["tokens"]))
        self.assertIn("strokeColor=#3B8BBA", hit["tokens"][0])
        self.assertIn("dashed=1", hit["tokens"][0])
        self.assertNotIn("dashPattern=", hit["tokens"][0])

    def test_lookup_azure_vnet_prefers_swimlane(self) -> None:
        for query in ("VNet", "Virtual Network", "Virtual Networks"):
            with self.subTest(query=query):
                hit = resolve_shape("azure", query)
                assert hit is not None
                self.assertEqual(hit["kind"], "group")
                self.assertTrue(hit["style"].startswith("swimlane;"))
                self.assertIn("strokeWidth=4", hit["style"])
                self.assertIn("container=1", hit["style"])
                self.assertEqual(hit["size"], "500x350")
                self.assertNotIn("Virtual_Networks.svg", hit["style"])
                self.assertTrue(hit["tokens"])
                self.assertTrue(all(token.startswith("azure.group:") for token in hit["tokens"]))
                self.assertIn("strokeWidth=4", hit["tokens"][0])

    def test_lookup_azure_resource_group_and_subscription(self) -> None:
        rg = resolve_shape("azure", "Resource Group")
        assert rg is not None
        self.assertEqual(rg["kind"], "group")
        self.assertIn("strokeColor=#CBCBCB", rg["style"])
        sub = resolve_shape("azure", "Subscription")
        assert sub is not None
        self.assertEqual(sub["kind"], "group")
        self.assertIn("strokeColor=#0078D4", sub["style"])

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
                "Subnet",
                "Resource Group",
                "Subscription",
            ],
            "gcp": [
                "Pub/Sub",
                "Dataflow",
                "BigQuery",
                "Looker",
                "Cloud Run",
                "Cloud SQL",
                "Cloud Load Balancing",
            ],
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

    def test_validate_distinguishes_aws_group_identities(self) -> None:
        cloud = resolve_shape("aws", "AWS Cloud")
        assert cloud is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="cloud" value="AWS Cloud" style="{cloud["style"]}" vertex="1" parent="1">
    <mxGeometry x="0" y="0" width="800" height="600" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "aws-cloud-only.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "aws", ["VPC"])
        self.assertIn("missing provider shape for VPC", issues)

    def test_validate_three_tier_azure(self) -> None:
        path = REFERENCES / "templates" / "three-tier-azure.drawio.xml"
        issues = collect_issues(
            path,
            "azure",
            [
                "App Service",
                "Azure SQL",
                "Application Gateway",
                "VNet",
                "Subnet",
                "Resource Group",
                "Subscription",
            ],
        )
        self.assertEqual(issues, [])

    def test_validate_accepts_azure_subnet_without_dash_pattern(self) -> None:
        """Templates may omit optional dashPattern; identity must still match."""
        subnet = resolve_shape("azure", "Subnet")
        assert subnet is not None
        # Drop dashPattern if present — mirrors older / hand-edited swimlanes.
        style = ";".join(
            part
            for part in subnet["style"].split(";")
            if part and not part.startswith("dashPattern=")
        )
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="subnet" value="Subnet" style="{style}" vertex="1" parent="1">
    <mxGeometry x="0" y="0" width="400" height="250" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "azure-subnet-no-dash.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "azure", ["Subnet"])
        self.assertEqual(issues, [])

    def test_validate_rejects_azure_vnet_product_icon(self) -> None:
        icon = (
            "aspect=fixed;html=1;shape=image;points=[];align=center;image;"
            "fontSize=12;image=img/lib/azure2/networking/Virtual_Networks.svg;"
        )
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="vnet" value="VNet" style="{icon}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="50" height="50" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "vnet-icon.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "azure", ["VNet"])
        self.assertIn("missing provider shape for VNet", issues)
        self.assertTrue(
            any("swimlane container" in issue for issue in issues),
            issues,
        )

    def test_validate_rejects_aws_shapes_in_azure_diagram(self) -> None:
        alb = resolve_shape("aws", "ALB")
        assert alb is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="alb" value="Application Gateway" style="{alb["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="50" height="50" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "aws-in-azure.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "azure", ["Application Gateway"])
        self.assertTrue(any("foreign provider" in issue for issue in issues), issues)
        self.assertTrue(any("missing provider shape" in issue for issue in issues), issues)

    def test_validate_accepts_azure_subnet_swimlane(self) -> None:
        subnet = resolve_shape("azure", "Subnet")
        assert subnet is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="subnet" value="Subnet" style="{subnet["style"]}" vertex="1" parent="1">
    <mxGeometry x="0" y="0" width="400" height="250" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "azure-subnet.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "azure", ["Subnet"])
        self.assertEqual(issues, [])

    def test_validate_rejects_azure_vnet_swimlane_without_container(self) -> None:
        """Swimlane styling alone is not enough; Azure groups need container=1."""
        vnet = resolve_shape("azure", "VNet")
        assert vnet is not None
        style = ";".join(
            part for part in vnet["style"].split(";") if part and part != "container=1"
        )
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="vnet" value="VNet" style="{style}" vertex="1" parent="1">
    <mxGeometry x="0" y="0" width="500" height="350" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "vnet-no-container.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "azure", ["VNet"])
        self.assertIn("missing provider shape for VNet", issues)

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
        card_xml = emit_gcp_service_card(pubsub, x=20, y=20, cell_id="card-pubsub")
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  {card_xml}
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "pubsub.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "gcp", ["Pub/Sub"])
        self.assertEqual(issues, [])

    def test_validate_rejects_standalone_gcp_icon(self) -> None:
        pubsub = resolve_shape("gcp", "Pub/Sub")
        assert pubsub is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="pubsub" value="Pub/Sub" style="{pubsub["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="30" height="30" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "standalone.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "gcp", ["Pub/Sub"])
        self.assertTrue(
            any("Service Card" in issue for issue in issues),
            issues,
        )

    def test_validate_rejects_aws_shapes_in_gcp_diagram(self) -> None:
        alb = resolve_shape("aws", "ALB")
        assert alb is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="alb" value="Load Balancer" style="{alb["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="50" height="50" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "aws-in-gcp.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "gcp", ["Cloud Load Balancing"])
        self.assertTrue(any("foreign provider" in issue for issue in issues), issues)
        self.assertTrue(any("missing provider shape" in issue for issue in issues), issues)

    def test_validate_rejects_gcp_icon_with_non_card_parent(self) -> None:
        pubsub = resolve_shape("gcp", "Pub/Sub")
        assert pubsub is not None
        # part=1 under a logical group — not a white Service Card wrapper.
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="group" value="Ingest" style="rounded=1;fillColor=#E3F2FD;strokeColor=#90CAF9;" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="200" height="120" as="geometry" />
  </mxCell>
  <mxCell id="pubsub" value="Pub/Sub" style="{pubsub["style"]};part=1;" vertex="1" parent="group">
    <mxGeometry x="20" y="20" width="30" height="30" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "fake-card.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "gcp", ["Pub/Sub"])
        self.assertTrue(
            any("Service Card" in issue for issue in issues),
            issues,
        )

    def test_validate_allows_custom_svg_in_aws_diagram(self) -> None:
        alb = resolve_shape("aws", "ALB")
        assert alb is not None
        # Non-catalog embedded SVG must not be treated as a foreign GCP token.
        custom = (
            "shape=image;image=data:image/svg+xml,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0Lz48L3N2Zz4=;"
        )
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="alb" value="ALB" style="{alb["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="50" height="50" as="geometry" />
  </mxCell>
  <mxCell id="badge" value="" style="{custom}" vertex="1" parent="1">
    <mxGeometry x="100" y="20" width="20" height="20" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "aws-custom-svg.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "aws", ["ALB"])
        self.assertEqual(issues, [])

    def test_validate_rejects_gcp_catalog_image_in_aws_diagram(self) -> None:
        alb = resolve_shape("aws", "ALB")
        pubsub = resolve_shape("gcp", "Pub/Sub")
        assert alb is not None and pubsub is not None
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="alb" value="ALB" style="{alb["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="50" height="50" as="geometry" />
  </mxCell>
  <mxCell id="pubsub" value="Pub/Sub" style="{pubsub["style"]}" vertex="1" parent="1">
    <mxGeometry x="100" y="20" width="30" height="30" as="geometry" />
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "gcp-in-aws.drawio"
            diagram.write_text(xml, encoding="utf-8")
            issues = collect_issues(diagram, "aws", ["ALB"])
        self.assertTrue(
            any("foreign provider" in issue and "GCP catalog image" in issue for issue in issues),
            issues,
        )

    def test_validate_multi_cloud_with_allow_providers(self) -> None:
        alb = resolve_shape("aws", "ALB")
        pubsub = resolve_shape("gcp", "Pub/Sub")
        assert alb is not None and pubsub is not None
        card_xml = emit_gcp_service_card(pubsub, x=120, y=20, cell_id="card-pubsub")
        xml = f"""\
<mxfile><diagram><mxGraphModel><root>
  <mxCell id="0" />
  <mxCell id="1" parent="0" />
  <mxCell id="alb" value="ALB" style="{alb["style"]}" vertex="1" parent="1">
    <mxGeometry x="20" y="20" width="50" height="50" as="geometry" />
  </mxCell>
  {card_xml}
</root></mxGraphModel></diagram></mxfile>
"""
        with tempfile.TemporaryDirectory() as directory:
            diagram = Path(directory) / "multi-cloud.drawio"
            diagram.write_text(xml, encoding="utf-8")
            blocked = collect_issues(diagram, "aws", ["ALB"])
            allowed = collect_issues(diagram, "aws", ["ALB"], allow_providers=["gcp"])
            gcp_ok = collect_issues(diagram, "gcp", ["Pub/Sub"], allow_providers=["aws"])
        self.assertTrue(any("foreign provider" in issue for issue in blocked), blocked)
        self.assertEqual(allowed, [])
        self.assertEqual(gcp_ok, [])

    def test_lookup_cli_emits_gcp_service_card(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "lookup_shape.py"),
                "--provider",
                "gcp",
                "--card",
                "--x",
                "40",
                "--y",
                "80",
                "--label",
                "Ingest",
                "--category",
                "Pub/Sub",
                "Pub/Sub",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('id="card-pubsub"', proc.stdout)
        self.assertIn("part=1", proc.stdout)
        self.assertIn("fillColor=#ffffff", proc.stdout)
        self.assertIn('width="160"', proc.stdout)
        self.assertIn("data:image/svg+xml", proc.stdout)
        self.assertIn('parent="card-pubsub"', proc.stdout)
        self.assertIn('x="40"', proc.stdout)
        self.assertIn('y="80"', proc.stdout)
        self.assertIn("Ingest", proc.stdout)


if __name__ == "__main__":
    unittest.main()
