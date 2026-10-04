#!/usr/bin/env python3
"""Re-export edge-crossing SVG fixtures with the official draw.io CLI.

With no arguments, re-exports the three starter templates and rewrites
starter-exports.json. With DRAWIO NAME pairs, exports each diagram to
NAME.svg and copies it to NAME.drawio. Embedded image data is dropped:
the crossing check reads geometry only.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[3] / "plugins" / "drawio" / "skills" / "cloud-diagram"
TEMPLATES = SKILL / "references" / "templates"
STARTERS = ("three-tier-aws", "three-tier-azure", "three-tier-gcp")
MANIFEST = HERE / "starter-exports.json"
_DATA_HREF_RE = re.compile(r'(href=")data:[^"]*"')


def export_stripped(diagram: Path, out_svg: Path) -> None:
    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "export.svg"
        subprocess.run(
            ["bash", str(SKILL / "scripts" / "export_diagram.sh"), str(diagram), str(raw)],
            check=True,
        )
        out_svg.write_text(
            _DATA_HREF_RE.sub(r'\1"', raw.read_text(encoding="utf-8")), encoding="utf-8"
        )


def refresh_starters() -> None:
    digests = {}
    for name in STARTERS:
        starter = TEMPLATES / f"{name}.drawio.xml"
        export_stripped(starter, HERE / f"{name}.svg")
        digests[name] = hashlib.sha256(starter.read_bytes()).hexdigest()
    MANIFEST.write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv:
        refresh_starters()
        return 0
    if len(argv) % 2:
        print("usage: refresh.py [DRAWIO NAME]...", file=sys.stderr)
        return 2
    for diagram, name in zip(argv[0::2], argv[1::2], strict=True):
        source = Path(diagram)
        shutil.copyfile(source, HERE / f"{name}.drawio")
        export_stripped(source, HERE / f"{name}.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
