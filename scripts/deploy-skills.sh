#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS_DIR="$REPO_DIR/harnesses"
PLUGINS_DIR="$REPO_DIR/plugins"

HARNESS=""
SCOPE="user"
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
  --skill <name>            Canonical skill name; may be repeated
  --all                     Deploy every canonical skill
  --scope <user|project>    Install scope (default: user)
  --project-root <path>     Project root for project-scoped installs
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
  case "$path" in
    \~)
      printf '%s\n' "$HOME"
      ;;
    \~/*)
      printf '%s\n' "$HOME/${path:2}"
      ;;
    *)
      printf '%s\n' "$path"
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
except Exception as exc:
    print(f"Error: invalid harness manifest {label}: {exc}", file=sys.stderr)
    raise SystemExit(1)
value = data.get(key)
if not isinstance(value, str) or not value.strip():
    print(f"Error: invalid harness manifest {label}: missing or empty {key}", file=sys.stderr)
    raise SystemExit(1)
print(value)
PY
}

resolve_skill_dir() {
  local name="$1"
  python3 - "$REPO_DIR" "$name" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from skill_eval.core import EvalError, resolve_skill

try:
    print(resolve_skill(Path(sys.argv[1]), sys.argv[2]))
except EvalError as exc:
    print(f"Error: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
}

add_skill() {
  local name="$1"
  case "$name" in
    skills/*)
      name="${name#skills/}"
      ;;
    plugins/*/skills/*)
      name="${name##*/}"
      ;;
  esac
  [[ "$name" != */* && "$name" != "." && "$name" != ".." ]] || fail "invalid skill name: $1"
  resolve_skill_dir "$name" >/dev/null || fail "missing skill: $name"
  if [[ -z "${SEEN_SKILLS[$name]:-}" ]]; then
    SEEN_SKILLS["$name"]=1
    SKILL_NAMES+=("$name")
  fi
}

expand_bundle_members() {
  local selected=("${SKILL_NAMES[@]}")
  local skill_name member
  SKILL_NAMES=()
  SEEN_SKILLS=()
  for skill_name in "${selected[@]}"; do
    while IFS= read -r member; do
      [[ -n "$member" ]] || continue
      add_skill "$member"
    done < <(
      python3 - "$REPO_DIR" "$skill_name" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from plugin_repository import PluginRepository

repo = PluginRepository.load(Path(sys.argv[1]))
bundle = repo.owner_of(sys.argv[2])
plugin = repo.plugin(bundle)
members = ", ".join(sorted(skill.value for skill in plugin.skills))
print(
    f"skill {sys.argv[2]!r} belongs to plugin {bundle.value!r}; "
    f"installing members: {members}",
    file=sys.stderr,
)
for skill_id in sorted(plugin.skills, key=lambda item: item.value):
    print(skill_id.value)
PY
    )
  done
}

add_all_skills() {
  while IFS= read -r skill_md; do
    add_skill "$(basename "$(dirname "$skill_md")")"
  done < <(find "$PLUGINS_DIR" -mindepth 4 -maxdepth 4 -type f -path '*/skills/*/SKILL.md' | sort)
}

install_skill() {
  local src="$1" dst="$2"
  if [[ -L "$dst" ]]; then
    if (( DRY_RUN )); then
      echo "remove symlink $dst"
    fi
  elif [[ -e "$dst" && ! -d "$dst" ]]; then
    fail "existing non-directory path blocks deployment: $dst"
  elif [[ -d "$dst" ]] && (( DRY_RUN )); then
    echo "remove directory $dst"
  fi

  if (( DRY_RUN )); then
    echo "copy runtime $src $dst"
  else
    python3 "$REPO_DIR/scripts/package_skill.py" "$src" "$dst"
  fi
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

HARNESS_FILE="$HARNESS_DIR/$HARNESS.json"
[[ -f "$HARNESS_FILE" ]] || fail "unknown harness: $HARNESS"
(( ALL )) && add_all_skills
[[ ${#SKILL_NAMES[@]} -gt 0 ]] || fail "select skills with --skill or --all"
if (( ! ALL )); then
  expand_bundle_members
fi

USER_INSTALL_ROOT="$(read_manifest_value "$HARNESS_FILE" user_install_root "$HARNESS")"
PROJECT_INSTALL_ROOT="$(read_manifest_value "$HARNESS_FILE" project_install_root "$HARNESS")"
if [[ "$SCOPE" == "user" ]]; then
  TARGET_ROOT="$(expand_home "$USER_INSTALL_ROOT")"
else
  [[ -n "$PROJECT_ROOT" ]] || PROJECT_ROOT="$(pwd)"
  TARGET_ROOT="$PROJECT_ROOT/$PROJECT_INSTALL_ROOT"
fi

if (( DRY_RUN )); then
  echo "mkdir -p $TARGET_ROOT"
else
  mkdir -p "$TARGET_ROOT"
fi

echo "Harness: $HARNESS"
echo "Scope: $SCOPE"
echo "Target: $TARGET_ROOT"

for skill_name in "${SKILL_NAMES[@]}"; do
  skill_src="$(resolve_skill_dir "$skill_name")"
  install_skill "$skill_src" "$TARGET_ROOT/$skill_name"
done

echo "Deployment complete"
