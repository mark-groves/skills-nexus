#!/usr/bin/env python3
"""The drawio-shapes fetch, extract, and generate steps fail closed on bad input."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "plugins" / "drawio" / "skills" / "drawio-shapes"
FETCH = SKILL / "scripts" / "fetch_sidebar.sh"
EXTRACT = SKILL / "scripts" / "extract.py"
GENERATE = SKILL / "scripts" / "generate_catalog.py"
SIDEBARS = SKILL / "fixtures" / "sidebars"
EXTRACTED = SKILL / "fixtures" / "extracted"

GOOD_SIDEBAR = "Sidebar.prototype.addAWS4Palette = function() {};\n"
FAKE_GH = """#!/usr/bin/env bash
case "$*" in
  *contents/*) [[ -n "${FAKE_SHA:-}" ]] || { echo "proxyconnect: refused" >&2; exit 1; }
               printf '%s\\n' "$FAKE_SHA" ;;
  *git/blobs/*) [[ "$*" == *"git/blobs/${FAKE_SHA:-}"* && -n "${FAKE_SHA:-}" ]] || exit 1
                printf '%s\\n' "${FAKE_CONTENT:-}" ;;
  *) exit 1 ;;
esac
"""


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), capture_output=True, text=True, check=False, env=env)


class FetchSidebarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH, encoding="utf-8")
        (bin_dir / "gh").chmod(0o755)
        self.dest = self.tmp / "working"
        self.dest.mkdir()
        self.target = self.dest / "Sidebar-AWS4.js"
        self.target.write_text(GOOD_SIDEBAR, encoding="utf-8")
        self.env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}

    def fetch(self, **extra: str) -> subprocess.CompletedProcess[str]:
        return run("bash", str(FETCH), "Sidebar-AWS4.js", str(self.dest), env={**self.env, **extra})

    def test_gh_error_exits_nonzero_and_keeps_the_good_sidebar(self) -> None:
        completed = self.fetch()
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), GOOD_SIDEBAR)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["Sidebar-AWS4.js"])

    def test_empty_blob_exits_nonzero_and_keeps_the_good_sidebar(self) -> None:
        completed = self.fetch(FAKE_SHA=git_blob_sha(b"new content\n"), FAKE_CONTENT="")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("does not match blob", completed.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), GOOD_SIDEBAR)

    def test_verified_blob_replaces_the_sidebar(self) -> None:
        data = b"Sidebar.prototype.addAWS4Palette = function() { /* new */ };\n"
        completed = self.fetch(
            FAKE_SHA=git_blob_sha(data), FAKE_CONTENT=base64.b64encode(data).decode()
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(self.target.read_bytes(), data)


class ExtractFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_empty_sidebar_is_an_unknown_library_error(self) -> None:
        sidebar = self.tmp / "Sidebar-GCPIcons.js"
        sidebar.write_text("", encoding="utf-8")
        output = self.tmp / "GCPIcons_extracted.json"
        completed = run("python3", str(EXTRACT), str(sidebar), "-q", "-o", str(output))
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Unknown library", completed.stderr)
        self.assertFalse(output.exists())

    def test_recorded_skip_still_exits_zero(self) -> None:
        output = self.tmp / "AWS4b_extracted.json"
        completed = run(
            "python3", str(EXTRACT), str(SIDEBARS / "aws4b-skip.js"), "-q", "-o", str(output)
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("AWS18", json.loads(output.read_text(encoding="utf-8"))["skip_reason"])


class GenerateFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.inputs = self.tmp / "in"
        shutil.copytree(EXTRACTED, self.inputs)
        self.out = self.tmp / "out"

    def extract_into(self, sidebar: Path, name: str) -> None:
        completed = run("python3", str(EXTRACT), str(sidebar), "-q", "-o", str(self.inputs / name))
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def generate(self, *providers: str) -> subprocess.CompletedProcess[str]:
        return run(
            "python3",
            str(GENERATE),
            *providers,
            "--input-dir",
            str(self.inputs),
            "--output-dir",
            str(self.out),
        )

    def rewrite(self, name: str, **fields: object) -> None:
        path = self.inputs / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(fields)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_skip_record_is_refused(self) -> None:
        self.extract_into(SIDEBARS / "aws4b-skip.js", "AWS4_extracted.json")
        completed = self.generate("aws")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("AWS4_extracted.json is a skip record for AWS4b", completed.stderr)
        self.assertFalse((self.out / "aws4-shapes.generated.md").exists())

    def test_unknown_library_is_refused(self) -> None:
        self.rewrite("GCPIcons_extracted.json", library="Unknown", categories={})
        completed = self.generate("gcp")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(
            "GCPIcons_extracted.json has library Unknown, expected GCPIcons", completed.stderr
        )

    def test_empty_input_is_refused(self) -> None:
        self.rewrite("GCPIcons_extracted.json", categories={"Generic": []})
        completed = self.generate("gcp")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("GCPIcons_extracted.json has 0 entries", completed.stderr)

    def test_one_bad_provider_writes_no_fragments(self) -> None:
        self.rewrite("Azure2_extracted.json", categories={})
        completed = self.generate("all")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(list(self.out.glob("*.md")) if self.out.exists() else [], [])

    def test_unresolved_aws_calls_still_generate_the_resolved_entries(self) -> None:
        self.extract_into(SIDEBARS / "aws4-unresolved.js", "AWS4_extracted.json")
        completed = self.generate("aws")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        fragment = (self.out / "aws4-shapes.generated.md").read_text(encoding="utf-8")
        self.assertEqual(
            [line for line in fragment.splitlines() if line.startswith("### ")], ["### EC2"]
        )

    def test_card_glyph_beats_a_smaller_plain_icon(self) -> None:
        card_svg, plain_svg = "PHN2Zz5jYXJkPC9zdmc+", "PHN2Zz5wbGFpbjwvc3ZnPg=="
        self.rewrite(
            "GCP2_extracted.json",
            categories={
                "GeneralIcons": [],
                "Compute": [
                    {
                        "name": "Cloud GPUs",
                        "type": "product_card",
                        "base64_svg": card_svg,
                        "width": 30,
                        "height": 30,
                    }
                ],
                "IconsCompute": [
                    {
                        "name": "Cloud GPUs",
                        "type": "vertex_icon",
                        "base64_svg": plain_svg,
                        "width": 20,
                        "height": 20,
                    }
                ],
            },
        )
        completed = self.generate("gcp")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        fragment = (self.out / "gcp-shapes.generated.md").read_text(encoding="utf-8")
        self.assertIn(f"image/svg+xml,{card_svg};`\n- **Size:** 30x30", fragment)
        self.assertNotIn(plain_svg, fragment)

    def test_gcpicons_semicolon_fixture_generates_its_entry(self) -> None:
        self.extract_into(SIDEBARS / "gcpicons-semicolon.js", "GCPIcons_extracted.json")
        completed = self.generate("gcp")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        fragment = (self.out / "gcp-shapes.generated.md").read_text(encoding="utf-8")
        self.assertIn("### Generic\n", fragment)
        self.assertIn("PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==", fragment)


if __name__ == "__main__":
    unittest.main()
