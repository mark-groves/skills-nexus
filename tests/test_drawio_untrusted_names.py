#!/usr/bin/env python3
"""Untrusted draw.io names stay out of the shell and fail the allowlists."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLOUD = REPO_ROOT / "plugins" / "drawio" / "skills" / "cloud-diagram"
SHAPES = REPO_ROOT / "plugins" / "drawio" / "skills" / "drawio-shapes"
LOOKUP = CLOUD / "scripts" / "lookup_shape.py"
VALIDATE = CLOUD / "scripts" / "validate_diagram.py"
EXPORT = CLOUD / "scripts" / "export_diagram.sh"
CROSSINGS = CLOUD / "scripts" / "check_edge_crossings.py"
FETCH = SHAPES / "scripts" / "fetch_sidebar.sh"
EXTRACT = SHAPES / "scripts" / "extract.py"
GENERATE = SHAPES / "scripts" / "generate_catalog.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "cloud-diagram"
SIDEBARS = SHAPES / "fixtures" / "sidebars"

NAME_PATTERN = "^[A-Za-z0-9._-]+$"
DRAWIO_PATTERN = r"^[A-Za-z0-9._-]+\.drawio$"
BASH_FENCE = re.compile(r"```bash\n(.*?)```", re.DOTALL)

MALICIOUS_NAMES = (
    "ec2$(touch-marker)",
    "ec2`touch-marker`",
    'ec2"quoted',
    "ec2'quoted",
    "ec2\ntouch-marker",
    "ec2;touch-marker",
)
MALICIOUS_DIAGRAMS = (
    "a$(touch-marker).drawio",
    "a`touch-marker`.drawio",
    'a"b.drawio',
    "a'b.drawio",
    "a\nb.drawio",
    "a;b.drawio",
    "../a.drawio",
    "nested/a.drawio",
    ".drawio",
    "a.drawio.xml",
)


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        input=input,
    )


class AllowlistCliTests(unittest.TestCase):
    def test_lookup_argv_rejects_shell_metacharacters(self) -> None:
        for query in MALICIOUS_NAMES:
            with self.subTest(query=query):
                proc = run([sys.executable, str(LOOKUP), "--provider", "aws", query])
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn(NAME_PATTERN, proc.stderr)
                self.assertNotIn("MISS:", proc.stderr)

    def test_lookup_input_file_rejects_command_substitution_without_running_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "pwned"
            payload = f"ec2$(touch {marker})"
            request = root / "diagram-lookup.json"
            request.write_text(json.dumps({"provider": "aws", "query": payload}), encoding="utf-8")
            proc = run([sys.executable, str(LOOKUP), "--input-file", str(request)])
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn(NAME_PATTERN, proc.stderr)
            self.assertFalse(marker.exists())

    def test_lookup_input_file_rejects_each_metacharacter_class(self) -> None:
        fields = ("query", "label", "category", "cell_id")
        for field in fields:
            for value in MALICIOUS_NAMES:
                with self.subTest(field=field, value=value):
                    body: dict[str, object] = {
                        "provider": "gcp",
                        "query": "pub-sub",
                        "card": True,
                        "label": "Ingest",
                        "category": "Messaging",
                    }
                    body[field] = value
                    proc = self._lookup_file(body)
                    self.assertEqual(proc.returncode, 2, proc.stderr)
                    self.assertIn(NAME_PATTERN, proc.stderr)

    def test_lookup_input_file_accepts_an_allowlisted_query(self) -> None:
        proc = self._lookup_file({"provider": "aws", "query": "ec2"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("title: EC2", proc.stdout)

    def test_lookup_stdin_accepts_an_allowlisted_card(self) -> None:
        proc = run(
            [sys.executable, str(LOOKUP), "--input-file", "-"],
            input=json.dumps(
                {
                    "provider": "gcp",
                    "query": "pub-sub",
                    "card": True,
                    "x": 40,
                    "y": 80,
                    "label": "Ingest",
                    "category": "Pub-Sub",
                }
            ),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('id="card-pubsub-40x80"', proc.stdout)
        self.assertIn("Ingest", proc.stdout)

    def test_validate_input_file_rejects_malicious_filenames(self) -> None:
        for diagram in MALICIOUS_DIAGRAMS:
            with self.subTest(diagram=diagram):
                proc = self._validate_file({"diagram": diagram, "provider": "aws"})
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn(DRAWIO_PATTERN, proc.stderr)

    def test_validate_input_file_rejects_malicious_service_names(self) -> None:
        for service in MALICIOUS_NAMES:
            with self.subTest(service=service):
                proc = self._validate_file(
                    {
                        "diagram": "architecture.drawio",
                        "provider": "aws",
                        "require_services": ["ec2", service],
                    }
                )
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn(NAME_PATTERN, proc.stderr)

    def test_validate_input_file_accepts_a_basename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(FIXTURES / "bad-edge.drawio", root / "bad-edge.drawio")
            request = root / "diagram-validate.json"
            request.write_text(
                json.dumps({"diagram": "bad-edge.drawio"}),
                encoding="utf-8",
            )
            proc = run(
                [sys.executable, str(VALIDATE), "--input-file", "diagram-validate.json"],
                cwd=root,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn("missing mxGeometry", proc.stderr)

    def test_validate_argv_rejects_require_services_with_spaces_or_metacharacters(self) -> None:
        diagram = str(FIXTURES / "bad-edge.drawio")
        for services in ("ec2,healthcare api", "ec2$(id)", "ec2;id", "ec2`id`"):
            with self.subTest(services=services):
                proc = run(
                    [
                        sys.executable,
                        str(VALIDATE),
                        diagram,
                        "--provider",
                        "aws",
                        "--require-services",
                        services,
                    ]
                )
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn(NAME_PATTERN, proc.stderr)

    def test_developer_fixture_paths_still_validate(self) -> None:
        proc = run([sys.executable, str(VALIDATE), str(FIXTURES / "bad-edge.drawio")])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing mxGeometry", proc.stderr)

    def test_export_input_file_does_not_execute_a_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "pwned"
            request = root / "diagram-export.json"
            request.write_text(
                json.dumps(
                    {
                        "input": f"a$(touch {marker}).drawio",
                        "output": "a.svg",
                        "format": "svg",
                    }
                ),
                encoding="utf-8",
            )
            proc = run(["bash", str(EXPORT), "--input-file", str(request)])
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn(DRAWIO_PATTERN, proc.stderr)
            self.assertFalse(marker.exists())
            self.assertNotIn("draw.io CLI not found", proc.stderr)

    def test_export_rejects_metacharacters_in_output_and_positional_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "diagram-export.json"
            request.write_text(
                json.dumps(
                    {
                        "input": "architecture.drawio",
                        "output": "a;b.svg",
                        "format": "svg",
                    }
                ),
                encoding="utf-8",
            )
            rejected = run(["bash", str(EXPORT), "--input-file", str(request)])
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.assertIn("svg|png|pdf", rejected.stderr)
            positional = run(
                ["bash", str(EXPORT), "a$(id).drawio", "a.svg"],
            )
            self.assertEqual(positional.returncode, 2, positional.stderr)
            missing = run(
                ["bash", str(EXPORT), "missing-architecture.drawio", "missing-architecture.svg"],
            )
            self.assertEqual(missing.returncode, 1, missing.stderr)
            self.assertIn("not found", missing.stderr)

    def test_crossings_input_file_rejects_malicious_names(self) -> None:
        for diagram, svg in (
            ("a$(id).drawio", "a.svg"),
            ("architecture.drawio", "a`id`.svg"),
            ("../architecture.drawio", "architecture.svg"),
            ("architecture.drawio", "nested/architecture.svg"),
        ):
            with self.subTest(diagram=diagram, svg=svg):
                proc = self._json_cli(
                    CROSSINGS,
                    "diagram-crossings.json",
                    {"diagram": diagram, "svg": svg},
                )
                self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_fetch_input_file_rejects_unquoted_style_names(self) -> None:
        for name in ("Sidebar-AWS4.js;id", "Sidebar-$(id).js", "../Sidebar-AWS4.js", "notes.txt"):
            with self.subTest(name=name):
                proc = self._json_cli(FETCH, "sidebar-request.json", {"file": name}, bash=True)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn("Sidebar-", proc.stderr)
                self.assertNotIn("blob", proc.stderr.lower())

    def test_extract_input_file_rejects_and_accepts_allowlisted_paths(self) -> None:
        rejected = self._json_cli(
            EXTRACT,
            "extract-request.json",
            {"file": "working/$(id).js", "output": "working/out.json"},
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertIn("working/Sidebar-", rejected.stderr)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "working"
            working.mkdir()
            shutil.copyfile(SIDEBARS / "aws4b-skip.js", working / "Sidebar-AWS4b.js")
            request = root / "extract-request.json"
            request.write_text(
                json.dumps(
                    {
                        "file": "working/Sidebar-AWS4b.js",
                        "output": "working/aws4b_extracted.json",
                    }
                ),
                encoding="utf-8",
            )
            proc = run(
                [sys.executable, str(EXTRACT), "--input-file", "extract-request.json"],
                cwd=root,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((working / "aws4b_extracted.json").is_file())

    def test_generate_input_file_rejects_metacharacters_in_provider(self) -> None:
        proc = self._json_cli(
            GENERATE,
            "catalog-request.json",
            {"providers": ["aws$(id)"], "output_dir": "catalog-out"},
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(NAME_PATTERN, proc.stderr)

    def _lookup_file(self, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
        return self._json_cli(LOOKUP, "diagram-lookup.json", payload)

    def _validate_file(self, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
        return self._json_cli(VALIDATE, "diagram-validate.json", payload)

    def _json_cli(
        self,
        program: Path,
        request_name: str,
        payload: dict[str, object],
        *,
        bash: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / request_name
            request.write_text(json.dumps(payload), encoding="utf-8")
            command = ["bash", str(program)] if bash else [sys.executable, str(program)]
            return run([*command, "--input-file", request_name], cwd=root)


class SkillInstructionTests(unittest.TestCase):
    def test_drawio_bash_fences_do_not_interpolate_placeholders(self) -> None:
        root = REPO_ROOT / "plugins" / "drawio"
        fences = []
        for doc in sorted(root.rglob("*.md")):
            fences.extend(BASH_FENCE.findall(doc.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(fences), 6)
        for fence in fences:
            self.assertNotIn("<", fence)
            self.assertNotIn("$(<", fence)
            self.assertNotRegex(fence, r"\$\([^)]*<")

    def test_skills_document_the_allowlists_and_input_file(self) -> None:
        cloud = (CLOUD / "SKILL.md").read_text(encoding="utf-8")
        shapes = (SHAPES / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(NAME_PATTERN, cloud)
        self.assertIn(DRAWIO_PATTERN, cloud)
        self.assertIn("--input-file diagram-lookup.json", cloud)
        self.assertIn("--input-file diagram-validate.json", cloud)
        self.assertIn("--input-file diagram-export.json", cloud)
        self.assertIn("--input-file diagram-crossings.json", cloud)
        self.assertIn("--input-file sidebar-request.json", shapes)
        self.assertIn("--input-file extract-request.json", shapes)
        self.assertIn("--input-file catalog-request.json", shapes)
        self.assertIn("^Sidebar-[A-Za-z0-9]+\\.js$", shapes)
        for text in (cloud, shapes):
            self.assertIn("backticks", text)
            self.assertNotIn('"<service>"', text)
            self.assertNotIn('"<Filename>"', text)
            self.assertNotIn("<FILE>", text)


if __name__ == "__main__":
    unittest.main()
