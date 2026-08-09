"""Fixture tests for PluginRepository (pre-cutover scaffold)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "scripts"))

from plugin_repository import (  # noqa: E402
    EXPECTED_BUNDLES,
    PLUGIN_SCHEMA_ID,
    BundleId,
    PluginRepository,
    PluginRepositoryError,
    SkillId,
)


def _write_skill(skills_root: Path, name: str) -> None:
    skill = skills_root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use for {name}.\n---\n\nBody.\n",
        encoding="utf-8",
    )


def _write_plugin(plugins_root: Path, bundle: str, skills: set[str]) -> Path:
    root = plugins_root / bundle
    root.mkdir(parents=True)
    manifest = {
        "$schema": PLUGIN_SCHEMA_ID,
        "name": bundle,
        "version": "1.0.0",
        "description": f"{bundle} plugin",
    }
    (root / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    skills_root = root / "skills"
    skills_root.mkdir()
    for skill in sorted(skills):
        _write_skill(skills_root, skill)
    return root


def _write_locked_repo(repo_root: Path) -> None:
    plugins = repo_root / "plugins"
    plugins.mkdir()
    for bundle, skills in EXPECTED_BUNDLES.items():
        _write_plugin(plugins, bundle, set(skills))
    (repo_root / "evals").mkdir()


class PluginRepositoryTests(unittest.TestCase):
    def test_load_accepts_locked_companion_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_locked_repo(root)
            repository = PluginRepository.load(root)
            self.assertEqual(
                {bundle.value for bundle in repository.plugins},
                set(EXPECTED_BUNDLES),
            )
            self.assertEqual(repository.owner_of("commit"), BundleId("git-workflow"))
            self.assertEqual(repository.owner_of("pr"), BundleId("git-workflow"))
            self.assertEqual(repository.owner_of("cloud-diagram"), BundleId("drawio"))
            self.assertEqual(
                repository.skill("skill-architect").source_dir,
                (root / "plugins/skill-architect/skills/skill-architect").resolve(),
            )

    def test_load_rejects_partial_bundle_membership(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_locked_repo(root)
            (root / "plugins/git-workflow/skills/pr").rename(root / "pr-moved")
            with self.assertRaisesRegex(PluginRepositoryError, "git-workflow"):
                PluginRepository.load(root)

    def test_load_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_locked_repo(root)
            outside = root / "outside.txt"
            outside.write_text("secret\n", encoding="utf-8")
            target = root / "plugins/git-workflow/skills/commit/leak.txt"
            target.symlink_to(outside)
            with self.assertRaisesRegex(PluginRepositoryError, "symlink"):
                PluginRepository.load(root)

    def test_load_rejects_invalid_manifest_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_locked_repo(root)
            manifest = root / "plugins/git-workflow/plugin.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["$schema"] = "https://example.invalid/schema.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(PluginRepositoryError, r"\$schema"):
                PluginRepository.load(root)

    def test_load_rejects_duplicate_skill_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plugins = root / "plugins"
            plugins.mkdir()
            _write_plugin(plugins, "git-workflow", {"commit", "pr"})
            _write_plugin(plugins, "drawio", {"cloud-diagram", "drawio-shapes"})
            # Illegal second owner for commit inside skill-architect slot.
            _write_plugin(plugins, "skill-architect", {"commit"})
            with self.assertRaisesRegex(PluginRepositoryError, "owned by both|skills must be"):
                PluginRepository.load(root)

    def test_skill_id_rejects_unsafe_names(self) -> None:
        with self.assertRaises(PluginRepositoryError):
            SkillId("Commit")
        with self.assertRaises(PluginRepositoryError):
            SkillId("../escape")


if __name__ == "__main__":
    unittest.main()
