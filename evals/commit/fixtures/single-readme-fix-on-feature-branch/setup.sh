#!/usr/bin/env bash
set -euo pipefail

git branch -m main
# shellcheck disable=SC2016 # Literal backticks are Markdown code spans.
printf '# Widget API\n\nUse `widgte serve` to start the service.\n' > README.md
git add README.md
git commit -q -m 'docs: add service instructions'

git switch -q -c fix/readme-typo
# shellcheck disable=SC2016 # Literal backticks are Markdown code spans.
printf '# Widget API\n\nUse `widget serve` to start the service.\n' > README.md
