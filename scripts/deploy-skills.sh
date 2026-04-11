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

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy-skills.sh --harness <name> [options]

Options:
  --harness <name>          Harness adapter name from harnesses/*.json
  --scope <user|project>    Install scope (default: user)
  --project-root <path>     Project root for project-scoped installs
  --mode <symlink|copy>     Install mode (default: symlink)
  --skill <name>            Skill to deploy (repeatable)
  --all                     Deploy all skills
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
      SKILL_NAMES+=("$2")
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

if ! command -v jq >/dev/null 2>&1; then
  fail "jq is required"
fi

if (( ALL )); then
  while IFS= read -r dir; do
    SKILL_NAMES+=("$(basename "$dir")")
  done < <(find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d | sort)
fi

if [[ ${#SKILL_NAMES[@]} -eq 0 ]]; then
  fail "select skills with --skill or use --all"
fi

USER_INSTALL_ROOT="$(jq -r '.user_install_root' "$HARNESS_FILE")"
PROJECT_INSTALL_ROOT="$(jq -r '.project_install_root' "$HARNESS_FILE")"

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
  link_or_copy "$src" "$dst"
done

echo "Deployment complete"
