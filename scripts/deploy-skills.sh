#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS_DIR="$REPO_DIR/harnesses"
SKILLS_DIR="$REPO_DIR/skills"
PORTABLE_SKILLS_DIR="$SKILLS_DIR/portable"
HARNESS_SKILLS_DIR="$SKILLS_DIR/harness"

HARNESS=""
SCOPE="user"
MODE=""
PROJECT_ROOT=""
DRY_RUN=0
ALL=0
ALL_PORTABLE=0
ALL_FOR_HARNESS=0
declare -a SKILL_SELECTORS=()
declare -a SKILL_IDS=()
declare -A SEEN_SKILLS=()
declare -A SEEN_INSTALL_NAMES=()

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy-skills.sh --harness <name> [options]

Options:
  --harness <name>          Harness manifest filename stem from harnesses/<name>.json
  --skill <id|name>         Skill to deploy; accepts portable/pr, harness/<harness>/name, or an unambiguous folder name
  --all                     Deploy portable skills plus skills for the selected harness
  --all-portable            Deploy every portable skill
  --all-for-harness         Deploy every skill for the selected harness
  --scope <user|project>    Install scope (default: user)
  --project-root <path>     Project root for project-scoped installs
  --mode <symlink|copy>     Install mode (default: symlink for user, copy for project; Codex user installs copy)
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

link_or_copy() {
  local src="$1" dst="$2"
  local removed_existing_symlink=0

  if [[ -L "$dst" ]]; then
    removed_existing_symlink=1
    if (( DRY_RUN )); then
      echo "remove symlink $dst"
    else
      rm "$dst"
    fi
  fi

  case "$MODE" in
    symlink)
      if [[ -e "$dst" && $removed_existing_symlink -eq 0 ]]; then
        echo "skip existing non-symlink: $dst" >&2
        return
      fi
      if (( DRY_RUN )); then
        echo "ln -s $src $dst"
      else
        ln -s "$src" "$dst"
      fi
      ;;
    copy)
      if [[ -e "$dst" ]]; then
        if [[ -d "$dst" ]]; then
          if (( DRY_RUN )); then
            echo "rm -rf $dst"
          else
            rm -rf "$dst"
          fi
        else
          fail "existing non-directory path blocks copy mode: $dst"
        fi
      fi
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

sanitize_codex_skill_copy() {
  local skill_md="$1"

  if (( DRY_RUN )); then
    echo "sanitize Codex frontmatter $skill_md"
    return
  fi

  python3 - "$skill_md" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    raise SystemExit(0)

end = text.find("\n---", 4)
if end == -1:
    raise SystemExit(0)

frontmatter = text[4:end].splitlines()
body = text[end:]
allowed = {"name", "description", "metadata"}
kept = []
keeping = False

for line in frontmatter:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        if keeping:
            kept.append(line)
        continue
    if line[0].isspace():
        if keeping:
            kept.append(line)
        continue

    key = line.split(":", 1)[0].strip()
    keeping = key in allowed
    if keeping:
        kept.append(line)

path.write_text("---\n" + "\n".join(kept).rstrip() + "\n" + body, encoding="utf-8")
PY
}

validate_codex_symlink_source() {
  local skill_md="$1"

  python3 - "$skill_md" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if not text.startswith("---\n"):
    raise SystemExit(0)

end = text.find("\n---", 4)
if end == -1:
    raise SystemExit(0)

allowed = {"name", "description", "metadata"}
extra = []
for line in text[4:end].splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or line[0].isspace():
        continue
    key = line.split(":", 1)[0].strip()
    if key not in allowed:
        extra.append(key)

if extra:
    print(
        "Error: Codex symlink installs require runtime-safe frontmatter in "
        f"{path}: {', '.join(sorted(extra))}",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
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

add_skill_id() {
  local skill_id="$1"
  local install_name
  install_name="$(basename "$skill_id")"

  if [[ -n "${SEEN_SKILLS[$skill_id]:-}" ]]; then
    return
  fi

  if [[ -n "${SEEN_INSTALL_NAMES[$install_name]:-}" ]]; then
    fail "multiple selected skills install as $install_name: ${SEEN_INSTALL_NAMES[$install_name]} and $skill_id"
  fi

  SEEN_SKILLS["$skill_id"]=1
  SEEN_INSTALL_NAMES["$install_name"]="$skill_id"
  SKILL_IDS+=("$skill_id")
}

add_skill_selector() {
  SKILL_SELECTORS+=("$1")
}

resolve_skill_selector() {
  local selector="$1"
  local skill_dir
  local rel

  if [[ "$selector" == */* ]]; then
    case "$selector" in
      portable/*)
        ;;
      harness/"$HARNESS"/*)
        ;;
      harness/*)
        local selector_harness="${selector#harness/}"
        selector_harness="${selector_harness%%/*}"
        fail "skill $selector is for harness $selector_harness, not $HARNESS"
        ;;
      *)
        fail "invalid skill selector: $selector"
        ;;
    esac
    skill_dir="$SKILLS_DIR/$selector"
    [[ -f "$skill_dir/SKILL.md" ]] || fail "missing skill: $selector"
    rel="${skill_dir#"$SKILLS_DIR/"}"
    printf '%s\n' "$rel"
    return
  fi

  local matches=()
  while IFS= read -r skill_md; do
    matches+=("$(dirname "${skill_md#"$SKILLS_DIR/"}")")
  done < <(
    find "$PORTABLE_SKILLS_DIR" "$HARNESS_SKILLS_DIR/$HARNESS" \
      -mindepth 2 -maxdepth 2 -type f -path "*/$selector/SKILL.md" 2>/dev/null | sort
  )

  case "${#matches[@]}" in
    0)
      fail "missing skill: $selector"
      ;;
    1)
      printf '%s\n' "${matches[0]}"
      ;;
    *)
      fail "ambiguous skill name $selector; use one of: ${matches[*]}"
      ;;
  esac
}

add_skills_from_root() {
  local root="$1"
  [[ -d "$root" ]] || return 0
  while IFS= read -r skill_md; do
    add_skill_id "$(dirname "${skill_md#"$SKILLS_DIR/"}")"
  done < <(find "$root" -mindepth 2 -maxdepth 2 -type f -name SKILL.md | sort)
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
      add_skill_selector "$2"
      shift 2
      ;;
    --all)
      ALL=1
      shift
      ;;
    --all-portable)
      ALL_PORTABLE=1
      shift
      ;;
    --all-for-harness)
      ALL_FOR_HARNESS=1
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
if [[ -z "$MODE" ]]; then
  case "$SCOPE" in
    user)
      if [[ "$HARNESS" == "codex" ]]; then
        MODE="copy"
      else
        MODE="symlink"
      fi
      ;;
    project)
      MODE="copy"
      ;;
  esac
fi
[[ "$MODE" == "symlink" || "$MODE" == "copy" ]] || fail "--mode must be symlink or copy"

HARNESS_FILE="$HARNESS_DIR/$HARNESS.json"
[[ -f "$HARNESS_FILE" ]] || fail "unknown harness: $HARNESS"

for selector in "${SKILL_SELECTORS[@]}"; do
  resolved_skill="$(resolve_skill_selector "$selector")"
  add_skill_id "$resolved_skill"
done

if (( ALL || ALL_PORTABLE )); then
  add_skills_from_root "$PORTABLE_SKILLS_DIR"
fi

if (( ALL || ALL_FOR_HARNESS )); then
  add_skills_from_root "$HARNESS_SKILLS_DIR/$HARNESS"
fi

if [[ ${#SKILL_IDS[@]} -eq 0 ]]; then
  fail "select skills with --skill, --all, --all-portable, or --all-for-harness"
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

for skill_id in "${SKILL_IDS[@]}"; do
  src="$SKILLS_DIR/$skill_id"
  install_name="$(basename "$skill_id")"
  dst="$TARGET_ROOT/$install_name"
  [[ -d "$src" ]] || fail "missing skill: $skill_id"
  [[ -f "$src/SKILL.md" ]] || fail "missing skill: $skill_id"
  if [[ "$HARNESS" == "codex" && "$MODE" == "symlink" ]]; then
    validate_codex_symlink_source "$src/SKILL.md"
  fi
  link_or_copy "$src" "$dst"
  if [[ "$HARNESS" == "codex" && "$MODE" == "copy" ]]; then
    sanitize_codex_skill_copy "$dst/SKILL.md"
  fi
done

echo "Deployment complete"
