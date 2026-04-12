#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS_DIR="$REPO_DIR/harnesses"
SKILLS_DIR="$REPO_DIR/skills"

HARNESS=""
SCOPE="user"
MODE="symlink"
PROJECT_ROOT=""
DRY_RUN=0
ALL=0
declare -a SKILL_NAMES=()
declare -A SEEN_SKILLS=()

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy-skills.sh --harness <name> [options]

Options:
  --harness <name>          Harness manifest filename stem from harnesses/<name>.json
  --skill <name>            Skill to deploy (repeatable, primary path)
  --all                     Convenience: deploy every skill directory containing SKILL.md
  --scope <user|project>    Install scope (default: user)
  --project-root <path>     Project root for project-scoped installs
  --mode <symlink|copy>     Install mode (default: symlink)
  --dry-run                 Print actions without changing anything
  --help                    Show this message
EOF
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

expand_home() {
  local path="$1"
  if [[ "$path" == "~" ]]; then
    printf '%s\n' "$HOME"
  elif [[ "$path" == "~/"* ]]; then
    printf '%s\n' "$HOME/${path:2}"
  else
    printf '%s\n' "$path"
  fi
}

link_or_copy() {
  local src="$1" dst="$2"

  if [[ -L "$dst" ]]; then
    if (( DRY_RUN )); then
      echo "remove symlink $dst"
    else
      rm "$dst"
    fi
  elif [[ -e "$dst" ]]; then
    echo "skip existing non-symlink: $dst" >&2
    return
  fi

  case "$MODE" in
    symlink)
      if (( DRY_RUN )); then
        echo "ln -s $src $dst"
      else
        ln -s "$src" "$dst"
      fi
      ;;
    copy)
      if (( DRY_RUN )); then
        echo "cp -R $src $dst"
      else
        cp -R "$src" "$dst"
      fi
      ;;
    *)
      fail "unsupported mode: $MODE"
      ;;
  esac
}

read_manifest_value() {
  local file="$1" key="$2" label="$3"

  python3 - "$file" "$key" "$label" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
label = sys.argv[3]

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:  # pragma: no cover - shell surfaces the error
    print(f"Error: invalid harness manifest {label}: {exc}", file=sys.stderr)
    raise SystemExit(1)

value = data.get(key)
if not isinstance(value, str) or not value.strip():
    print(f"Error: invalid harness manifest {label}: missing or empty {key}", file=sys.stderr)
    raise SystemExit(1)

print(value)
PY
}

add_skill() {
  local skill_name="$1"

  if [[ -n "${SEEN_SKILLS[$skill_name]:-}" ]]; then
    return
  fi

  SEEN_SKILLS["$skill_name"]=1
  SKILL_NAMES+=("$skill_name")
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --harness)
      [[ $# -ge 2 ]] || fail "--harness requires a value"
      HARNESS="$2"
      shift 2
      ;;
    --scope)
      [[ $# -ge 2 ]] || fail "--scope requires a value"
      SCOPE="$2"
      shift 2
      ;;
    --project-root)
      [[ $# -ge 2 ]] || fail "--project-root requires a value"
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --mode)
      [[ $# -ge 2 ]] || fail "--mode requires a value"
      MODE="$2"
      shift 2
      ;;
    --skill)
      [[ $# -ge 2 ]] || fail "--skill requires a value"
      add_skill "$2"
      shift 2
      ;;
    --all)
      ALL=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -n "$HARNESS" ]] || fail "--harness is required"
[[ "$SCOPE" == "user" || "$SCOPE" == "project" ]] || fail "--scope must be user or project"
[[ "$MODE" == "symlink" || "$MODE" == "copy" ]] || fail "--mode must be symlink or copy"

HARNESS_FILE="$HARNESS_DIR/$HARNESS.json"
[[ -f "$HARNESS_FILE" ]] || fail "unknown harness: $HARNESS"

if (( ALL )); then
  while IFS= read -r skill_md; do
    add_skill "$(basename "$(dirname "$skill_md")")"
  done < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -type f -name SKILL.md | sort)
fi

if [[ ${#SKILL_NAMES[@]} -eq 0 ]]; then
  fail "select skills with --skill or use --all"
fi

USER_INSTALL_ROOT="$(read_manifest_value "$HARNESS_FILE" user_install_root "$HARNESS")"
PROJECT_INSTALL_ROOT="$(read_manifest_value "$HARNESS_FILE" project_install_root "$HARNESS")"

case "$SCOPE" in
  user)
    TARGET_ROOT="$(expand_home "$USER_INSTALL_ROOT")"
    ;;
  project)
    if [[ -z "$PROJECT_ROOT" ]]; then
      PROJECT_ROOT="$(pwd)"
    fi
    TARGET_ROOT="$PROJECT_ROOT/$PROJECT_INSTALL_ROOT"
    ;;
esac

if (( DRY_RUN )); then
  echo "mkdir -p $TARGET_ROOT"
else
  mkdir -p "$TARGET_ROOT"
fi

echo "Harness: $HARNESS"
echo "Scope: $SCOPE"
echo "Mode: $MODE"
echo "Target: $TARGET_ROOT"

for skill_name in "${SKILL_NAMES[@]}"; do
  src="$SKILLS_DIR/$skill_name"
  dst="$TARGET_ROOT/$skill_name"
  [[ -d "$src" ]] || fail "missing skill: $skill_name"
  [[ -f "$src/SKILL.md" ]] || fail "missing skill: $skill_name"
  link_or_copy "$src" "$dst"
done

echo "Deployment complete"
