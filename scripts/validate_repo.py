#!/usr/bin/env python3
"""Validate the steady-state skills-nexus repo contract."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import re


REPO_DIR = Path(__file__).resolve().parents[1]
README_PATH = REPO_DIR / "README.md"
SKILLS_DIR = REPO_DIR / "skills"
HARNESS_DIR = REPO_DIR / "harnesses"
CLOUD_DIAGRAM_REFS = REPO_DIR / "skills" / "cloud-diagram" / "references"
DRAWIO_FIXTURES = REPO_DIR / "skills" / "drawio-shapes" / "fixtures" / "extracted"
DRAWIO_GENERATOR = REPO_DIR / "skills" / "drawio-shapes" / "scripts" / "generate_catalog.py"
CLOUD_IMPORTER = REPO_DIR / "skills" / "cloud-diagram" / "scripts" / "import_shape_catalog.py"
GENERATED_MARKER = "<!-- GENERATED BELOW -->"

EXPECTED_README_HEADINGS = [
    "Purpose",
    "Repo Contract",
    "Install/Deploy Usage",
    "Validation",
    "Maintainer Workflow For Shape-Catalog Refresh",
]
EXPECTED_HARNESS_KEYS = {"user_install_root", "project_install_root"}
HARD_CODED_INSTALL_ROOTS = (
    "~/.claude/skills",
    "~/.codex/skills",
    "$HOME/.claude/skills",
    "$HOME/.codex/skills",
    ".claude/skills",
    ".codex/skills",
)
FORBIDDEN_DISCOVERY_PATTERNS = ("git rev-parse --show-toplevel",)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
SIBLING_PATH_RE = re.compile(r"(^|[^A-Za-z0-9_./-])\.\./[A-Za-z0-9_.-]+/")
ALLOWED_INLINE_PREFIXES = ("scripts/", "references/", "assets/", "evals/", "working/")

ERRORS: list[str] = []


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


def validate_readme() -> None:
    text = read_text(README_PATH)
    headings = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    if headings != EXPECTED_README_HEADINGS:
        fail(
            "README headings must be exactly: "
            + ", ".join(EXPECTED_README_HEADINGS)
        )

    forbidden = ("catalog/skills.json", "docs/migration-plan.md")
    for snippet in forbidden:
        if snippet in text:
            fail(f"README still references removed scaffolding: {snippet}")

    required_snippets = (
        "bash scripts/deploy-skills.sh",
        "--skill",
        "--all",
        "bash scripts/check-skills.sh",
        "`drawio-shapes` skill",
        "`cloud-diagram` skill",
    )
    for snippet in required_snippets:
        if snippet not in text:
            fail(f"README is missing expected command/interface text: {snippet}")


def validate_generated_junk() -> None:
    for file_path in git_ls_files("skills"):
        rel = repo_relative(file_path)
        if "/working/" in rel:
            fail(f"Tracked generated junk under working/: {rel}")
        if "__pycache__" in rel:
            fail(f"Tracked generated junk under __pycache__: {rel}")
        if rel.endswith(".pyc"):
            fail(f"Tracked generated junk .pyc file: {rel}")


def validate_harness_manifests() -> None:
    manifests = sorted(HARNESS_DIR.glob("*.json"))
    if not manifests:
        fail("No harness manifests found")
        return

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
        if actual_keys != EXPECTED_HARNESS_KEYS:
            extra = sorted(actual_keys - EXPECTED_HARNESS_KEYS)
            missing = sorted(EXPECTED_HARNESS_KEYS - actual_keys)
            if extra:
                fail(f"Unexpected keys in {rel}: {', '.join(extra)}")
            if missing:
                fail(f"Missing keys in {rel}: {', '.join(missing)}")

        for key in EXPECTED_HARNESS_KEYS:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                fail(f"Empty or non-string {key} in {rel}")


def validate_portability_patterns(skill_dir: Path) -> None:
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
        if SIBLING_PATH_RE.search(text):
            fail(f"Forbidden sibling-path reference in {rel}")


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


def validate_skill_contract(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail(f"Skill directory missing SKILL.md: {repo_relative(skill_dir)}")
        return

    evals_json = skill_dir / "evals" / "evals.json"
    if evals_json.exists():
        try:
            payload = json.loads(read_text(evals_json))
        except Exception as exc:
            fail(f"Invalid JSON in {repo_relative(evals_json)}: {exc}")
        else:
            if payload.get("skill_name") != skill_dir.name:
                fail(
                    f"skill_name mismatch in {repo_relative(evals_json)}: "
                    f"expected {skill_dir.name!r}, found {payload.get('skill_name')!r}"
                )

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


def validate_deploy_script(valid_skills: list[str]) -> None:
    harnesses = sorted(manifest.stem for manifest in HARNESS_DIR.glob("*.json"))
    if not harnesses or not valid_skills:
        return

    explicit_skill = valid_skills[0]

    for harness in harnesses:
        run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            harness,
            "--skill",
            explicit_skill,
            "--dry-run",
            expect_success=True,
            label=f"deploy dry-run for {harness} with explicit skill",
        )
        run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            harness,
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

    manifest = json.loads(read_text(HARNESS_DIR / f"{harnesses[0]}.json"))
    project_install_root = manifest["project_install_root"]

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        destination = project_root / project_install_root / explicit_skill

        run_command(
            "bash",
            "scripts/deploy-skills.sh",
            "--harness",
            harnesses[0],
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
            harnesses[0],
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
            harnesses[0],
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
            harnesses[0],
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
            harnesses[0],
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
            harnesses[0],
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
    validate_readme()
    valid_skills = validate_skills_root()
    validate_harness_manifests()
    validate_generated_junk()
    validate_deploy_script(valid_skills)
    validate_handoff_smoke_tests()

    if ERRORS:
        for error in ERRORS:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    print("Repo validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
