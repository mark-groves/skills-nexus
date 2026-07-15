#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src docs
printf 'def export_rows(rows):\n    return list(rows)\n' > src/export.py
printf '# Export guide\n\nUse the export command to save rows.\n' > docs/export.md
git add src/export.py docs/export.md
git commit -q -m 'feat: add basic export support'

git switch -q -c feat/export-csv
printf 'import csv\n\ndef export_rows(rows, output):\n    writer = csv.writer(output)\n    writer.writerows(rows)\n' > src/export.py
printf '# Export guide\n\nUse `export --format csv` to save comma-separated rows.\n' > docs/export.md
