#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status=0

check_pattern() {
  local pattern="$1"
  local label="$2"

  if rg -n "$pattern" "$REPO_DIR/skills"
  then
    echo "Found forbidden install-discovery pattern: $label" >&2
    status=1
  fi
}

check_pattern '~/.claude/skills' '~/.claude/skills'
check_pattern '~/.codex/skills' '~/.codex/skills'
check_pattern '\$HOME/\.claude/skills' '$HOME/.claude/skills'
check_pattern '\$HOME/\.codex/skills' '$HOME/.codex/skills'
check_pattern '\.claude/skills' '.claude/skills'
check_pattern '\.codex/skills' '.codex/skills'
check_pattern 'git rev-parse --show-toplevel' 'git rev-parse --show-toplevel'

if (( status == 0 )); then
  echo "Skill portability checks passed"
fi

exit "$status"
