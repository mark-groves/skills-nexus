#!/usr/bin/env python3
"""Guards for the bundled official draw.io installer."""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (
    REPO_ROOT
    / "plugins"
    / "drawio"
    / "skills"
    / "cloud-diagram"
    / "scripts"
    / "install-drawio-cli.sh"
)
WRAPPER = REPO_ROOT / "scripts" / "install-drawio-cli.sh"
SOURCE_MAP = (
    REPO_ROOT / "plugins" / "drawio" / "skills" / "drawio-shapes" / "references" / "source-map.md"
)


def installer_default_version() -> str:
    match = re.search(
        r'DRAWIO_VERSION="\$\{DRAWIO_VERSION:-([0-9.]+)\}"',
        INSTALLER.read_text(encoding="utf-8"),
    )
    assert match is not None, "installer default DRAWIO_VERSION not found"
    return match.group(1)


def pinned_sidebar_version() -> str:
    match = re.search(r"\(draw\.io ([0-9.]+), ", SOURCE_MAP.read_text(encoding="utf-8"))
    assert match is not None, "draw.io pin not found in source-map.md"
    return match.group(1)


class InstallDrawioCliTests(unittest.TestCase):
    def test_installer_is_bundled_with_skill(self) -> None:
        self.assertTrue(INSTALLER.is_file())
        self.assertTrue(os.access(INSTALLER, os.X_OK))
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn(
            "plugins/drawio/skills/cloud-diagram/scripts/install-drawio-cli.sh",
            wrapper,
        )

    def test_installer_matches_pinned_sidebar_release(self) -> None:
        """Stencils newer than the CLI (e.g. sustainability, s3_files) export blank."""
        self.assertEqual(installer_default_version(), pinned_sidebar_version())

    def test_marker_write_avoids_root_shell_interpolation(self) -> None:
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertNotRegex(
            source,
            r"""bash\s+-c\s+["'].*DRAWIO_VERSION""",
        )
        self.assertIn('need_root tee "${MARKER}"', source)

    def test_rejects_non_semver_drawio_version(self) -> None:
        env = os.environ.copy()
        env["DRAWIO_VERSION"] = '31.1.5"; echo PWNED; #'
        completed = subprocess.run(
            ["bash", str(INSTALLER)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("DRAWIO_VERSION must be MAJOR.MINOR.PATCH", completed.stderr)

    def test_probe_prefers_binary_over_stale_marker_text(self) -> None:
        """Regression: MARKER alone must not short-circuit the version probe."""
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("probe_installed_version", source)
        self.assertRegex(
            source,
            re.compile(
                r"installed=\"\$\(probe_installed_version \|\| true\)\".*"
                r'\[\[ "\$\{installed\}" == "\$\{DRAWIO_VERSION\}" \]\]',
                re.DOTALL,
            ),
        )
        # Marker may still be written for operators, but the fast path must
        # call probe_installed_version (binary under xvfb), not read MARKER.
        fast_path = source.split('installed="$(probe_installed_version || true)"', 1)[0]
        self.assertNotIn("tr -d '[:space:]' <\"${MARKER}\"", fast_path)

    def test_stale_marker_does_not_block_idempotent_success(self) -> None:
        if os.environ.get("RUN_PRIVILEGED_DRAWIO_TESTS") != "1":
            self.skipTest("set RUN_PRIVILEGED_DRAWIO_TESTS=1 for host installer testing")
        if not Path("/opt/drawio/drawio").is_file():
            self.skipTest("official draw.io not installed in this environment")
        marker = Path("/usr/local/share/drawio-cli.version")
        previous = marker.read_text(encoding="utf-8") if marker.is_file() else None
        try:
            subprocess.run(
                ["sudo", "tee", str(marker)],
                input="99.9.9\n",
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run(
                ["bash", str(INSTALLER)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("already installed", completed.stdout)
            self.assertIn(installer_default_version(), completed.stdout)
        finally:
            if previous is None:
                subprocess.run(
                    ["sudo", "rm", "-f", str(marker)],
                    check=False,
                    capture_output=True,
                )
            else:
                subprocess.run(
                    ["sudo", "tee", str(marker)],
                    input=previous,
                    check=False,
                    capture_output=True,
                    text=True,
                )


if __name__ == "__main__":
    unittest.main()
