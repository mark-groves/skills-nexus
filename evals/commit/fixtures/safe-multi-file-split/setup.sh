#!/usr/bin/env bash
set -euo pipefail

git branch -m main
mkdir -p src
printf 'def export_rows(rows):\n    return list(rows)\n' > src/export.py
printf '__pycache__/\n' > .gitignore
git add src/export.py .gitignore
git commit -q -m 'feat: add basic export support'

git switch -q -c feat/export-csv
printf 'import csv\n\ndef export_rows(rows, output):\n    writer = csv.writer(output)\n    writer.writerows(rows)\n' > src/export.py
printf '__pycache__/\n.cache/\n' > .gitignore
