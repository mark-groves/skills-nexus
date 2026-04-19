#!/usr/bin/env python3
"""Validate the steady-state skills-nexus repo contract."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_DIR / "skills"
HARNESS_DIR = REPO_DIR / "harnesses"
CLOUD_DIAGRAM_REFS = REPO_DIR / "skills" / "cloud-diagram" / "references"
DRAWIO_FIXTURES = REPO_DIR / "skills" / "drawio-shapes" / "fixtures" / "extracted"
DRAWIO_GENERATOR = REPO_DIR / "skills" / "drawio-shapes" / "scripts" / "generate_catalog.py"
CLOUD_IMPORTER = REPO_DIR / "skills" / "cloud-diagram" / "scripts" / "import_shape_catalog.py"
GENERATED_MARKER = "<!-- GENERATED BELOW -->"

EXPECTED_HARNESS_KEYS = {"user_install_root", "project_install_root"}
REQUIRED_HARNESSES = {"agents", "claude-code", "codex", "cursor", "kiro"}
ALLOWED_FRONTMATTER_KEYS = {"name", "description", "license", "compatibility", "metadata"}
REQUIRED_EVAL_KEYS = {"skill_name", "trigger_evals", "behavior_evals"}
HARD_CODED_INSTALL_ROOTS = (
    "~/.agents/skills",
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.cursor/skills",
    "~/.kiro/skills",
    "$HOME/.agents/skills",
    "$HOME/.claude/skills",
    "$HOME/.codex/skills",
    "$HOME/.cursor/skills",
    "$HOME/.kiro/skills",
    ".agents/skills",
    ".claude/skills",
    ".codex/skills",
    ".cursor/skills",
    ".kiro/skills",
)
FORBIDDEN_DISCOVERY_PATTERNS = ("git rev-parse --show-toplevel",)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
FRONTMATTER_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")
PARENT_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:\.\./)+(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+/?)"
)
ALLOWED_INLINE_PREFIXES = ("scripts/", "references/", "assets/", "evals/", "working/")

ERRORS: list[str] = []
FrontmatterValue = str | dict[str, str]


def fail(message: str) -> None:
    ERRORS.append(message)


def repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_DIR))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def iter_skill_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in skill_dir.rglob("*"):
        if not path.is_file():
            continue
        if "working" in path.parts or "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def git_ls_files(*paths: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths],
        cwd=REPO_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return [REPO_DIR / item for item in result.stdout.split("\0") if item]


def run_command(*args: str, expect_success: bool, label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if expect_success and result.returncode != 0:
        fail(
            f"{label} failed with exit {result.returncode}: "
            f"{(result.stderr or result.stdout).strip()}"
        )
    if not expect_success and result.returncode == 0:
        fail(f"{label} unexpectedly succeeded")
    return result


def iter_inline_code_tokens(markdown_text: str) -> list[str]:
    tokens: list[str] = []
    in_fence = False
    for line in markdown_text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        tokens.extend(match.group(1) for match in INLINE_CODE_RE.finditer(line))
    return tokens


def is_explicit_skill_local_path(token: str) -> bool:
    if not token.startswith(ALLOWED_INLINE_PREFIXES):
        return False
    if any(ch in token for ch in (" ", "<", ">", "*", "?", "[", "]", "|")):
        return False
    if "://" in token:
        return False
    return True


def is_allowed_output_parent_path(path_ref: str) -> bool:
    parts = path_ref.rstrip("/").split("/")
    if not parts:
        return False

    parent_count = 0
    for part in parts:
        if part != "..":
            break
        parent_count += 1

    if parent_count not in (1, 2):
        return False
    if len(parts) <= parent_count:
        return False
    if parts[parent_count] != "raw":
        return False
    return all(part not in ("", ".", "..") for part in parts[parent_count:])


def extract_frontmatter_block(skill_md: Path) -> str | None:
    text = read_text(skill_md)
    lines = text.splitlines()
    rel = repo_relative(skill_md)

    if not lines or lines[0].strip() != "---":
        fail(f"SKILL.md must start with YAML frontmatter in {rel}")
        return None

    block_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---" and not line.startswith((" ", "\t")):
            return "\n".join(block_lines)
        block_lines.append(line)

    fail(f"SKILL.md frontmatter is missing a closing delimiter in {rel}")
    return None


def parse_single_quoted_yaml(value: str) -> str | None:
    parts: list[str] = []
    index = 1
    while index < len(value):
        char = value[index]
        if char == "'":
            if index + 1 < len(value) and value[index + 1] == "'":
                parts.append("'")
                index += 2
                continue
            trailing = value[index + 1 :].strip()
            if trailing:
                return None
            return "".join(parts)
        parts.append(char)
        index += 1
    return None


def parse_double_quoted_yaml(value: str) -> str | None:
    parts: list[str] = []
    index = 1
    escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "0": "\0",
        "a": "\a",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
    }

    while index < len(value):
        char = value[index]
        if char == '"':
            trailing = value[index + 1 :].strip()
            if trailing:
                return None
            return "".join(parts)
        if char != "\\":
            parts.append(char)
            index += 1
            continue

        index += 1
        if index >= len(value):
            return None

        escape = value[index]
        if escape in escapes:
            parts.append(escapes[escape])
            index += 1
            continue
        if escape in {"x", "u", "U"}:
            widths = {"x": 2, "u": 4, "U": 8}
            width = widths[escape]
            digits = value[index + 1 : index + 1 + width]
            if len(digits) != width or any(ch not in "0123456789abcdefABCDEF" for ch in digits):
                return None
            parts.append(chr(int(digits, 16)))
            index += 1 + width
            continue
        return None

    return None


def strip_yaml_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    index = 0

    while index < len(value):
        char = value[index]
        if in_single:
            if char == "'":
                if index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                in_single = False
            index += 1
            continue

        if in_double:
            if escaped:
                escaped = False
                index += 1
                continue
            if char == "\\":
                escaped = True
                index += 1
                continue
            if char == '"':
                in_double = False
            index += 1
            continue

        if char == "'":
            in_single = True
        elif char == '"':
            in_double = True
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        index += 1

    return value.rstrip()


def fold_yaml_lines(lines: list[str]) -> str:
    folded: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            folded.append("\n")
            previous_blank = True
            continue
        if folded and not previous_blank and not folded[-1].endswith("\n"):
            folded.append(" ")
        folded.append(line)
        previous_blank = False
    return "".join(folded)


def parse_indented_yaml_string_map(
    lines: list[str], start_index: int, rel: str, key: str
) -> tuple[dict[str, str], int] | tuple[None, None]:
    block_lines: list[str] = []
    index = start_index
    block_indent: int | None = None

    while index < len(lines):
        block_line = lines[index]
        stripped = block_line.strip()
        if not stripped:
            block_lines.append("")
            index += 1
            continue

        indent = len(block_line) - len(block_line.lstrip(" "))
        if indent == 0:
            break
        if block_indent is None:
            block_indent = indent
        if indent < block_indent:
            break
        block_lines.append(block_line[block_indent:])
        index += 1

    if block_indent is None:
        fail(f"Frontmatter mapping is missing content in {rel}: {key}")
        return None, None

    payload = parse_yaml_string_map("\n".join(block_lines), rel)
    if payload is None:
        return None, None
    if any(not isinstance(value, str) for value in payload.values()):
        fail(f"Frontmatter mapping values must be YAML strings in {rel}: {key}")
        return None, None

    return payload, index


def parse_yaml_string_map(frontmatter_text: str, rel: str) -> dict[str, FrontmatterValue] | None:
    lines = frontmatter_text.splitlines()
    payload: dict[str, FrontmatterValue] = {}
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            fail(f"Malformed frontmatter in {rel}: {line!r}")
            return None

        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not key or not FRONTMATTER_KEY_RE.fullmatch(key):
            fail(f"Malformed frontmatter in {rel}: {line!r}")
            return None

        value_text = strip_yaml_inline_comment(raw_value.lstrip())
        if not value_text:
            if key != "metadata":
                fail(f"Frontmatter value must be a YAML string in {rel}: {key}")
                return None

            metadata_payload, next_index = parse_indented_yaml_string_map(lines, index + 1, rel, key)
            if metadata_payload is None or next_index is None:
                return None
            payload[key] = metadata_payload
            index = next_index
            continue

        if value_text in {"|", "|-", "|+", ">", ">-", ">+"}:
            block_lines: list[str] = []
            index += 1
            block_indent: int | None = None
            while index < len(lines):
                block_line = lines[index]
                if not block_line.strip():
                    block_lines.append("")
                    index += 1
                    continue

                indent = len(block_line) - len(block_line.lstrip(" "))
                if indent == 0:
                    break
                if block_indent is None:
                    block_indent = indent
                if indent < block_indent:
                    break
                block_lines.append(block_line[block_indent:])
                index += 1

            if block_indent is None:
                fail(f"Frontmatter block scalar is missing content in {rel}: {key}")
                return None

            value = fold_yaml_lines(block_lines) if value_text.startswith(">") else "\n".join(block_lines)
            if not value_text.endswith("+"):
                value = value.rstrip("\n")
            payload[key] = value
            continue

        if value_text.startswith("'"):
            parsed = parse_single_quoted_yaml(value_text)
        elif value_text.startswith('"'):
            parsed = parse_double_quoted_yaml(value_text)
        else:
            if value_text.startswith(("[", "{", "]", "}")):
                fail(f"Frontmatter value must be a YAML string in {rel}: {key}")
                return None
            parsed = value_text

        if parsed is None:
            fail(f"Malformed YAML frontmatter in {rel}: {key}")
            return None

        payload[key] = parsed
        index += 1

    return payload


def parse_frontmatter(skill_md: Path) -> dict[str, FrontmatterValue] | None:
    rel = repo_relative(skill_md)
    frontmatter_text = extract_frontmatter_block(skill_md)
    if frontmatter_text is None:
        return None
    payload = parse_yaml_string_map(frontmatter_text, rel)
    if payload is None:
        return None
    return payload


def validate_generated_junk() -> None:
    for file_path in git_ls_files("skills"):
        rel = repo_relative(file_path)
        if "/working/" in rel:
            fail(f"Tracked generated junk under working/: {rel}")
        if "__pycache__" in rel:
            fail(f"Tracked generated junk under __pycache__: {rel}")
        if rel.endswith(".pyc"):
            fail(f"Tracked generated junk .pyc file: {rel}")


def validate_harness_manifests() -> dict[str, dict[str, str]]:
    manifests = sorted(HARNESS_DIR.glob("*.json"))
    if not manifests:
        fail("No harness manifests found")
        return {}

    harnesses = [manifest.stem for manifest in manifests]
    missing_harnesses = sorted(REQUIRED_HARNESSES - set(harnesses))
    if missing_harnesses:
        fail(f"Missing required harness manifests: {', '.join(missing_harnesses)}")

    valid_manifests: dict[str, dict[str, str]] = {}

    for manifest in manifests:
        rel = repo_relative(manifest)
        try:
            payload = json.loads(read_text(manifest))
        except Exception as exc:
            fail(f"Invalid JSON in {rel}: {exc}")
            continue

        if not isinstance(payload, dict):
            fail(f"Harness manifest must be a JSON object: {rel}")
            continue

        actual_keys = set(payload)
        is_valid = True
        if actual_keys != EXPECTED_HARNESS_KEYS:
            extra = sorted(actual_keys - EXPECTED_HARNESS_KEYS)
            missing = sorted(EXPECTED_HARNESS_KEYS - actual_keys)
            if extra:
                fail(f"Unexpected keys in {rel}: {', '.join(extra)}")
                is_valid = False
            if missing:
                fail(f"Missing keys in {rel}: {', '.join(missing)}")
                is_valid = False

        for key in EXPECTED_HARNESS_KEYS:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                fail(f"Empty or non-string {key} in {rel}")
                is_valid = False

        if is_valid:
            valid_manifests[manifest.stem] = {
                "user_install_root": payload["user_install_root"],
                "project_install_root": payload["project_install_root"],
            }

    return valid_manifests


def validate_portability_patterns(skill_dir: Path) -> None:
    sibling_skill_refs = [
        f"../{entry.name}/"
        for entry in SKILLS_DIR.iterdir()
        if entry.is_dir() and entry != skill_dir
    ]
    for file_path in iter_skill_files(skill_dir):
        text = read_text_if_possible(file_path)
        if text is None:
            continue
        rel = repo_relative(file_path)

        for pattern in HARD_CODED_INSTALL_ROOTS:
            if pattern in text:
                fail(f"Forbidden install root pattern in {rel}: {pattern}")
        for pattern in FORBIDDEN_DISCOVERY_PATTERNS:
            if pattern in text:
                fail(f"Forbidden repo discovery pattern in {rel}: {pattern}")
        for match in PARENT_PATH_RE.finditer(text):
            path_ref = match.group(1)
            if is_allowed_output_parent_path(path_ref):
                continue
            if any(path_ref.startswith(pattern) for pattern in sibling_skill_refs):
                fail(f"Forbidden sibling-skill path reference in {rel}: {path_ref}")
            else:
                fail(f"Forbidden parent-path reference in {rel}: {path_ref}")


def validate_skill_local_refs(skill_dir: Path, skill_md: Path) -> None:
    for token in iter_inline_code_tokens(read_text(skill_md)):
        if not is_explicit_skill_local_path(token):
            continue
        candidate = (skill_dir / token).resolve()
        try:
            candidate.relative_to(skill_dir.resolve())
        except ValueError:
            fail(f"Backticked path escapes skill directory in {repo_relative(skill_md)}: `{token}`")
            continue
        if not candidate.exists():
            fail(f"Backticked path missing in {repo_relative(skill_md)}: `{token}`")


def validate_frontmatter(skill_dir: Path, skill_md: Path) -> None:
    frontmatter = parse_frontmatter(skill_md)
    if frontmatter is None:
        return

    extra_keys = sorted(set(frontmatter) - ALLOWED_FRONTMATTER_KEYS)
    if extra_keys:
        fail(
            f"Unsupported canonical frontmatter keys in {repo_relative(skill_md)}: "
            + ", ".join(extra_keys)
        )

    name_value = frontmatter.get("name", "")
    name = name_value.strip() if isinstance(name_value, str) else ""
    if not name:
        fail(f"Missing name in {repo_relative(skill_md)}")
    elif not NAME_RE.fullmatch(name):
        fail(f"Invalid skill name in {repo_relative(skill_md)}: {name!r}")
    elif name != skill_dir.name:
        fail(
            f"Skill name must match folder name in {repo_relative(skill_md)}: "
            f"expected {skill_dir.name!r}, found {name!r}"
        )

    description_value = frontmatter.get("description", "")
    description = description_value.strip() if isinstance(description_value, str) else ""
    if not description:
        fail(f"Missing description in {repo_relative(skill_md)}")
    elif len(description) > 300:
        fail(f"Description is too long in {repo_relative(skill_md)}")

    for key in ("license", "compatibility"):
        value = frontmatter.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            fail(f"Empty optional frontmatter field {key!r} in {repo_relative(skill_md)}")

    metadata = frontmatter.get("metadata")
    if metadata is None:
        return
    if isinstance(metadata, str):
        if not metadata.strip():
            fail(f"Empty optional frontmatter field 'metadata' in {repo_relative(skill_md)}")
        return
    if not metadata:
        fail(f"Empty optional frontmatter field 'metadata' in {repo_relative(skill_md)}")
        return
    for metadata_key, metadata_value in metadata.items():
        if not metadata_value.strip():
            fail(
                f"Empty metadata value {metadata_key!r} in {repo_relative(skill_md)}"
            )


def validate_evals(skill_dir: Path) -> None:
    evals_json = skill_dir / "evals" / "evals.json"
    rel = repo_relative(evals_json)

    if not evals_json.is_file():
        fail(f"Missing evals/evals.json for skill: {repo_relative(skill_dir)}")
        return

    try:
        payload = json.loads(read_text(evals_json))
    except Exception as exc:
        fail(f"Invalid JSON in {rel}: {exc}")
        return

    if not isinstance(payload, dict):
        fail(f"Evals file must be a JSON object: {rel}")
        return

    actual_keys = set(payload)
    if actual_keys != REQUIRED_EVAL_KEYS:
        extra = sorted(actual_keys - REQUIRED_EVAL_KEYS)
        missing = sorted(REQUIRED_EVAL_KEYS - actual_keys)
        if extra:
            fail(f"Unexpected keys in {rel}: {', '.join(extra)}")
        if missing:
            fail(f"Missing keys in {rel}: {', '.join(missing)}")

    if payload.get("skill_name") != skill_dir.name:
        fail(
            f"skill_name mismatch in {rel}: expected {skill_dir.name!r}, "
            f"found {payload.get('skill_name')!r}"
        )

    trigger_evals = payload.get("trigger_evals")
    if not isinstance(trigger_evals, list) or not trigger_evals:
        fail(f"trigger_evals must be a non-empty list in {rel}")
    else:
        positives = 0
        negatives = 0
        for item in trigger_evals:
            if not isinstance(item, dict):
                fail(f"Each trigger eval must be an object in {rel}")
                continue
            required_keys = {"id", "query", "should_trigger"}
            if set(item) != required_keys:
                fail(f"Invalid trigger eval shape in {rel}: {item!r}")
                continue
            if not isinstance(item["query"], str) or not item["query"].strip():
                fail(f"Trigger eval query must be a non-empty string in {rel}")
            if not isinstance(item["should_trigger"], bool):
                fail(f"Trigger eval should_trigger must be boolean in {rel}")
                continue
            positives += int(item["should_trigger"])
            negatives += int(not item["should_trigger"])
        if positives < 2:
            fail(f"Need at least 2 positive trigger evals in {rel}")
        if negatives < 2:
            fail(f"Need at least 2 negative trigger evals in {rel}")

    behavior_evals = payload.get("behavior_evals")
    if not isinstance(behavior_evals, list) or not behavior_evals:
        fail(f"behavior_evals must be a non-empty list in {rel}")
    else:
        for item in behavior_evals:
            if not isinstance(item, dict):
                fail(f"Each behavior eval must be an object in {rel}")
                continue
            required_keys = {"id", "prompt", "expected_behavior", "fixtures", "checks"}
            if set(item) != required_keys:
                fail(f"Invalid behavior eval shape in {rel}: {item!r}")
                continue
            if not isinstance(item["prompt"], str) or not item["prompt"].strip():
                fail(f"Behavior eval prompt must be a non-empty string in {rel}")
            if (
                not isinstance(item["expected_behavior"], str)
                or not item["expected_behavior"].strip()
            ):
                fail(f"Behavior eval expected_behavior must be a non-empty string in {rel}")
            if not isinstance(item["fixtures"], list):
                fail(f"Behavior eval fixtures must be a list in {rel}")
            if not isinstance(item["checks"], list) or not item["checks"]:
                fail(f"Behavior eval checks must be a non-empty list in {rel}")
            else:
                for check in item["checks"]:
                    if not isinstance(check, str) or not check.strip():
                        fail(f"Behavior eval checks must contain non-empty strings in {rel}")


def validate_skill_contract(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail(f"Skill directory missing SKILL.md: {repo_relative(skill_dir)}")
        return

    validate_frontmatter(skill_dir, skill_md)
    validate_evals(skill_dir)
    validate_portability_patterns(skill_dir)
    validate_skill_local_refs(skill_dir, skill_md)


def validate_skills_root() -> list[str]:
    valid_skills: list[str] = []
    for entry in sorted(SKILLS_DIR.iterdir(), key=lambda path: path.name):
        if not entry.is_dir():
            fail(f"Unexpected file directly under skills/: {repo_relative(entry)}")
            continue

        if not (entry / "SKILL.md").is_file():
            fail(f"Immediate child of skills/ is not a valid skill: {repo_relative(entry)}")
            continue

        valid_skills.append(entry.name)
        validate_skill_contract(entry)

    if not valid_skills:
        fail("No valid skills found under skills/")
    return valid_skills


def validate_deploy_script(
    valid_skills: list[str], harness_manifests: dict[str, dict[str, str]]
) -> None:
    harnesses = sorted(harness_manifests)
    if not harnesses or not valid_skills:
        return

    explicit_skill = valid_skills[0]

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        for harness in harnesses:
            dry_run_explicit = run_command(
                "bash",
                "scripts/deploy-skills.sh",
                "--harness",
                harness,
                "--scope",
                "project",
                "--project-root",
                str(project_root),
                "--skill",
                explicit_skill,
                "--dry-run",
                expect_success=True,
                label=f"deploy dry-run for {harness} with explicit skill",
            )
            if "Mode: symlink" not in dry_run_explicit.stdout:
                fail(f"Default deploy mode must be symlink for {harness}")
            if "ln -s" not in dry_run_explicit.stdout:
                fail(f"Dry-run deploy should announce symlink creation for {harness}")

            run_command(
                "bash",
                "scripts/deploy-skills.sh",
                "--harness",
                harness,
                "--scope",
                "project",
                "--project-root",
                str(project_root),
                "--all",
                "--dry-run",
                expect_success=True,
                label=f"deploy dry-run for {harness} with --all",
            )

    unknown_harness = run_command(
        "bash",
        "scripts/deploy-skills.sh",
        "--harness",
        "does-not-exist",
        "--skill",
        explicit_skill,
        "--dry-run",
        expect_success=False,
        label="deploy unknown harness check",
    )
    if "unknown harness" not in unknown_harness.stderr.lower():
        fail("Unknown harness error message changed unexpectedly")

    unknown_skill = run_command(
        "bash",
        "scripts/deploy-skills.sh",
        "--harness",
        harnesses[0],
        "--skill",
        "does-not-exist",
        "--dry-run",
        expect_success=False,
        label="deploy unknown skill check",
    )
    if "missing skill" not in unknown_skill.stderr.lower():
        fail("Unknown skill error message changed unexpectedly")

    agents_manifest = harness_manifests.get("agents")
    if agents_manifest is None:
        return

    project_install_root = agents_manifest["project_install_root"]

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        destination = project_root / project_install_root / explicit_skill

        run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            "agents",
            "--scope",
            "project",
            "--project-root",
            str(project_root),
            "--mode",
            "copy",
            "--skill",
            explicit_skill,
            expect_success=True,
            label="copy-mode initial deploy",
        )
        if not destination.is_dir():
            fail("Copy-mode initial deploy did not create the skill directory")

        sentinel = destination / "stale.txt"
        sentinel.write_text("stale\n", encoding="utf-8")

        dry_run_redeploy = run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            "agents",
            "--scope",
            "project",
            "--project-root",
            str(project_root),
            "--mode",
            "copy",
            "--skill",
            explicit_skill,
            "--dry-run",
            expect_success=True,
            label="copy-mode redeploy dry-run",
        )
        if f"rm -rf {destination}" not in dry_run_redeploy.stdout:
            fail("Copy-mode dry-run did not announce removal of an existing destination directory")
        if f"cp -R {SKILLS_DIR / explicit_skill} {destination}" not in dry_run_redeploy.stdout:
            fail("Copy-mode dry-run did not announce copying after directory replacement")

        run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            "agents",
            "--scope",
            "project",
            "--project-root",
            str(project_root),
            "--mode",
            "copy",
            "--skill",
            explicit_skill,
            expect_success=True,
            label="copy-mode redeploy",
        )
        if sentinel.exists():
            fail("Copy-mode redeploy left stale copied content in place")

        shutil.rmtree(destination)
        destination.write_text("collision\n", encoding="utf-8")
        file_collision = run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            "agents",
            "--scope",
            "project",
            "--project-root",
            str(project_root),
            "--mode",
            "copy",
            "--skill",
            explicit_skill,
            expect_success=False,
            label="copy-mode file collision check",
        )
        if "existing non-directory path blocks copy mode" not in file_collision.stderr.lower():
            fail("Copy-mode file collision error message changed unexpectedly")

        symlink_destination = project_root / project_install_root / explicit_skill
        symlink_destination.unlink()
        run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            "agents",
            "--scope",
            "project",
            "--project-root",
            str(project_root),
            "--mode",
            "symlink",
            "--skill",
            explicit_skill,
            expect_success=True,
            label="symlink-mode initial deploy",
        )
        if not symlink_destination.is_symlink():
            fail("Symlink-mode initial deploy did not create a symlink")

        dry_run_symlink_redeploy = run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            "agents",
            "--scope",
            "project",
            "--project-root",
            str(project_root),
            "--mode",
            "symlink",
            "--skill",
            explicit_skill,
            "--dry-run",
            expect_success=True,
            label="symlink-mode redeploy dry-run",
        )
        if f"remove symlink {symlink_destination}" not in dry_run_symlink_redeploy.stdout:
            fail("Symlink-mode dry-run did not announce removal of an existing symlink")
        if f"ln -s {SKILLS_DIR / explicit_skill} {symlink_destination}" not in dry_run_symlink_redeploy.stdout:
            fail("Symlink-mode dry-run did not announce relinking after symlink replacement")
        if "skip existing non-symlink" in dry_run_symlink_redeploy.stderr.lower():
            fail("Symlink-mode dry-run incorrectly reported an existing symlink as a non-symlink collision")
        if not symlink_destination.is_symlink():
            fail("Symlink-mode dry-run should not mutate the existing symlink")


def validate_handoff_smoke_tests() -> None:
    tracked_refs = {
        path.name: read_text(path)
        for path in (
            CLOUD_DIAGRAM_REFS / "aws4-shapes.md",
            CLOUD_DIAGRAM_REFS / "gcp-shapes.md",
            CLOUD_DIAGRAM_REFS / "azure-shapes.md",
        )
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        fragments_dir = temp_root / "fragments"
        fragments_dir.mkdir()

        run_command(
            "python3",
            str(DRAWIO_GENERATOR),
            "--input-dir",
            str(DRAWIO_FIXTURES),
            "--output-dir",
            str(fragments_dir),
            "aws",
            "gcp",
            "azure",
            expect_success=True,
            label="drawio fragment generation smoke test",
        )

        expected_fragments = {
            "aws4-shapes.generated.md",
            "gcp-shapes.generated.md",
            "azure-shapes.generated.md",
        }
        actual_fragments = {path.name for path in fragments_dir.glob("*.generated.md")}
        if actual_fragments != expected_fragments:
            fail(
                "Generated fragment set mismatch: expected "
                f"{sorted(expected_fragments)}, found {sorted(actual_fragments)}"
            )

        for path in (
            CLOUD_DIAGRAM_REFS / "aws4-shapes.md",
            CLOUD_DIAGRAM_REFS / "gcp-shapes.md",
            CLOUD_DIAGRAM_REFS / "azure-shapes.md",
        ):
            if read_text(path) != tracked_refs[path.name]:
                fail("drawio fragment generation mutated cloud-diagram references")

        run_command(
            "python3",
            str(CLOUD_IMPORTER),
            "--from-dir",
            str(fragments_dir),
            "--check-only",
            "aws",
            "gcp",
            "azure",
            expect_success=True,
            label="cloud-diagram import check-only smoke test",
        )

        temp_refs = temp_root / "references"
        shutil.copytree(CLOUD_DIAGRAM_REFS, temp_refs)
        run_command(
            "python3",
            str(CLOUD_IMPORTER),
            "--from-dir",
            str(fragments_dir),
            "--references-dir",
            str(temp_refs),
            "aws",
            "gcp",
            "azure",
            expect_success=True,
            label="cloud-diagram import write-mode smoke test",
        )

        expectations = {
            "aws4-shapes.md": (
                "A complete catalog of 2 unique AWS4 shapes",
                "### Lambda",
                "# AWS4 Shape Catalog for draw.io",
            ),
            "gcp-shapes.md": (
                "(4 entries).",
                "### Big Query (GCPIcons)",
                "# GCP Shape Catalog for draw.io",
            ),
            "azure-shapes.md": (
                "A complete catalog of 2 unique Azure2 service shapes",
                "### Virtual Machine",
                "# Azure Shape Catalog for draw.io",
            ),
        }
        for filename, (summary_snippet, entry_snippet, title_snippet) in expectations.items():
            updated = read_text(temp_refs / filename)
            if GENERATED_MARKER not in updated:
                fail(f"Imported reference lost generated marker: {filename}")
            if summary_snippet not in updated:
                fail(f"Imported reference missing refreshed summary text: {filename}")
            if entry_snippet not in updated:
                fail(f"Imported reference missing expected generated entry: {filename}")
            if title_snippet not in updated.split(GENERATED_MARKER, 1)[0]:
                fail(f"Imported reference did not preserve prelude content: {filename}")


def main() -> int:
    valid_skills = validate_skills_root()
    harnesses = validate_harness_manifests()
    validate_generated_junk()
    validate_deploy_script(valid_skills, harnesses)
    validate_handoff_smoke_tests()

    if ERRORS:
        for error in ERRORS:
            print(f"Error: {error}")
        return 1

    print("Repo validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
