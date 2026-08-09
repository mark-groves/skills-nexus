"""Canonical Agent Plugin repository index (Option A topology).

Callers load one PluginRepository; membership, containment, and uniqueness are
enforced at the boundary. Canonical skills live under
``plugins/<bundle>/skills/<name>/``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLUGIN_SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SAFE_SEGMENT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")

# Validation oracle for locked companion bundles. Operational membership is
# still derived from on-disk plugin trees after this oracle passes.
EXPECTED_BUNDLES: Mapping[str, frozenset[str]] = {
    "git-workflow": frozenset({"commit", "pr"}),
    "drawio": frozenset({"cloud-diagram", "drawio-shapes"}),
    "skill-architect": frozenset({"skill-architect"}),
}


class PluginRepositoryError(RuntimeError):
    """Raised when plugin topology or manifests fail closed."""


def require_safe_segment(value: str, *, kind: str) -> str:
    text = value.strip()
    if text != value or not SAFE_SEGMENT_RE.fullmatch(text):
        raise PluginRepositoryError(f"invalid {kind} {value!r}")
    return text


@dataclass(frozen=True, order=True)
class BundleId:
    value: str

    def __post_init__(self) -> None:
        require_safe_segment(self.value, kind="bundle id")


@dataclass(frozen=True, order=True)
class SkillId:
    value: str

    def __post_init__(self) -> None:
        require_safe_segment(self.value, kind="skill id")


@dataclass(frozen=True)
class SkillPackage:
    id: SkillId
    source_dir: Path
    owner: BundleId


@dataclass(frozen=True)
class PluginPackage:
    id: BundleId
    root: Path
    manifest_path: Path
    skills: Mapping[SkillId, SkillPackage]


@dataclass(frozen=True)
class PluginRepository:
    root: Path
    plugins: Mapping[BundleId, PluginPackage]
    skills: Mapping[SkillId, SkillPackage]
    evals_root: Path

    @classmethod
    def load(cls, repo_root: Path) -> PluginRepository:
        root = repo_root.resolve()
        plugins_root = root / "plugins"
        evals_root = root / "evals"
        if plugins_root.is_symlink() or not plugins_root.is_dir():
            raise PluginRepositoryError(
                f"plugins must be a real directory (no symlink): {plugins_root}"
            )

        discovered: dict[BundleId, PluginPackage] = {}
        skills: dict[SkillId, SkillPackage] = {}

        for child in sorted(plugins_root.iterdir(), key=lambda path: path.name):
            if child.name.startswith("."):
                continue
            if child.is_symlink():
                raise PluginRepositoryError(f"plugin path may not be a symlink: {child}")
            if not child.is_dir():
                raise PluginRepositoryError(f"unexpected non-directory under plugins/: {child}")
            package = _load_plugin_package(child)
            if package.id in discovered:
                raise PluginRepositoryError(f"duplicate bundle id {package.id.value!r}")
            discovered[package.id] = package
            for skill_id, skill in package.skills.items():
                if skill_id in skills:
                    raise PluginRepositoryError(
                        f"skill id {skill_id.value!r} owned by both "
                        f"{skills[skill_id].owner.value!r} and {package.id.value!r}"
                    )
                skills[skill_id] = skill

        _assert_expected_cover(discovered)

        if evals_root.exists():
            if evals_root.is_symlink() or not evals_root.is_dir():
                raise PluginRepositoryError(f"evals must be a real directory: {evals_root}")

        return cls(root=root, plugins=discovered, skills=skills, evals_root=evals_root)

    def skill(self, skill_id: SkillId | str) -> SkillPackage:
        key = skill_id if isinstance(skill_id, SkillId) else SkillId(skill_id)
        try:
            return self.skills[key]
        except KeyError as exc:
            raise PluginRepositoryError(f"unknown skill {key.value!r}") from exc

    def plugin(self, bundle_id: BundleId | str) -> PluginPackage:
        key = bundle_id if isinstance(bundle_id, BundleId) else BundleId(bundle_id)
        try:
            return self.plugins[key]
        except KeyError as exc:
            raise PluginRepositoryError(f"unknown plugin {key.value!r}") from exc

    def owner_of(self, skill_id: SkillId | str) -> BundleId:
        return self.skill(skill_id).owner


def _assert_expected_cover(discovered: Mapping[BundleId, PluginPackage]) -> None:
    expected_ids = {BundleId(name) for name in EXPECTED_BUNDLES}
    found_ids = set(discovered)
    if found_ids != expected_ids:
        missing = sorted(bundle.value for bundle in expected_ids - found_ids)
        extra = sorted(bundle.value for bundle in found_ids - expected_ids)
        raise PluginRepositoryError(
            f"plugin set must exact-cover locked bundles; missing={missing}; extra={extra}"
        )
    for bundle_id, package in discovered.items():
        expected_skills = EXPECTED_BUNDLES[bundle_id.value]
        found_skills = {skill.value for skill in package.skills}
        if found_skills != expected_skills:
            raise PluginRepositoryError(
                f"plugin {bundle_id.value!r} skills must be {sorted(expected_skills)}, "
                f"found {sorted(found_skills)}"
            )


def _load_plugin_package(plugin_root: Path) -> PluginPackage:
    bundle_id = BundleId(plugin_root.name)
    manifest_path = plugin_root / "plugin.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PluginRepositoryError(f"missing plugin.json for {plugin_root}")
    manifest = _parse_plugin_manifest(manifest_path)
    if manifest["name"] != bundle_id.value:
        raise PluginRepositoryError(
            f"{manifest_path} name {manifest['name']!r} must match directory {bundle_id.value!r}"
        )

    skills_root = plugin_root / "skills"
    if skills_root.is_symlink() or not skills_root.is_dir():
        raise PluginRepositoryError(f"missing skills/ directory in {plugin_root}")

    skills: dict[SkillId, SkillPackage] = {}
    for child in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if child.name.startswith("."):
            continue
        if child.is_symlink():
            raise PluginRepositoryError(f"skill path may not be a symlink: {child}")
        if not child.is_dir():
            raise PluginRepositoryError(f"unexpected non-directory under skills/: {child}")
        skill_id = SkillId(child.name)
        skill_md = child / "SKILL.md"
        if skill_md.is_symlink() or not skill_md.is_file():
            raise PluginRepositoryError(f"missing SKILL.md for {child}")
        _assert_tree_has_no_symlinks(child)
        skills[skill_id] = SkillPackage(id=skill_id, source_dir=child.resolve(), owner=bundle_id)

    if not skills:
        raise PluginRepositoryError(f"plugin {bundle_id.value!r} has no skills")

    _assert_tree_has_no_symlinks(plugin_root)
    return PluginPackage(
        id=bundle_id,
        root=plugin_root.resolve(),
        manifest_path=manifest_path.resolve(),
        skills=skills,
    )


def _parse_plugin_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PluginRepositoryError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PluginRepositoryError(f"{path} must be a JSON object")

    allowed = {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise PluginRepositoryError(f"{path} has unknown fields: {unknown}")

    schema = payload.get("$schema")
    if schema != PLUGIN_SCHEMA_ID:
        raise PluginRepositoryError(
            f"{path}.$schema must be {PLUGIN_SCHEMA_ID!r}, found {schema!r}"
        )
    name = payload.get("name")
    if not isinstance(name, str) or not PLUGIN_NAME_RE.fullmatch(name):
        raise PluginRepositoryError(f"{path}.name is invalid: {name!r}")
    if len(name) > 64:
        raise PluginRepositoryError(f"{path}.name exceeds 64 characters")

    if "version" in payload and not isinstance(payload["version"], str):
        raise PluginRepositoryError(f"{path}.version must be a string")
    if "description" in payload and not isinstance(payload["description"], str):
        raise PluginRepositoryError(f"{path}.description must be a string")
    if "homepage" in payload and not isinstance(payload["homepage"], str):
        raise PluginRepositoryError(f"{path}.homepage must be a string")
    if "repository" in payload and not isinstance(payload["repository"], str):
        raise PluginRepositoryError(f"{path}.repository must be a string")
    if "license" in payload and not isinstance(payload["license"], str):
        raise PluginRepositoryError(f"{path}.license must be a string")
    if "keywords" in payload:
        keywords = payload["keywords"]
        if not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords):
            raise PluginRepositoryError(f"{path}.keywords must be an array of strings")
    if "author" in payload:
        author = payload["author"]
        if not isinstance(author, dict):
            raise PluginRepositoryError(f"{path}.author must be an object")
        author_allowed = {"name", "email", "url"}
        author_unknown = sorted(set(author) - author_allowed)
        if author_unknown:
            raise PluginRepositoryError(f"{path}.author has unknown fields: {author_unknown}")
        for key, value in author.items():
            if not isinstance(value, str):
                raise PluginRepositoryError(f"{path}.author.{key} must be a string")
    if "extensions" in payload:
        extensions = payload["extensions"]
        if not isinstance(extensions, dict) or not all(
            isinstance(key, str) and isinstance(value, dict) for key, value in extensions.items()
        ):
            raise PluginRepositoryError(f"{path}.extensions must be an object of namespace objects")
    return payload


def _assert_tree_has_no_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PluginRepositoryError(f"symlink not allowed in plugin package: {path}")
