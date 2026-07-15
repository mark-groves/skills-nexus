import importlib.util
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_DIR / "scripts" / "validate_repo.py"
SPEC = importlib.util.spec_from_file_location("validate_repo", MODULE_PATH)
assert SPEC is not None
validate_repo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_repo)


class ValidateRepoFrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_repo.ERRORS.clear()

    def tearDown(self) -> None:
        validate_repo.ERRORS.clear()

    def write_skill_with_frontmatter(
        self, temp_root: Path, skill_name: str, frontmatter: str
    ) -> Path:
        skill_dir = temp_root / skill_name
        skill_dir.mkdir()
        frontmatter = textwrap.dedent(frontmatter).strip()
        (skill_dir / "SKILL.md").write_text(
            f"---\n{frontmatter}\n---\n# {skill_name}\n",
            encoding="utf-8",
        )
        return skill_dir

    def test_parse_yaml_string_map_accepts_structured_metadata(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            name: example-skill
            description: Example skill
            metadata:
              short-description: Short summary
              docs-url: https://example.com/skills/example-skill
              path-pattern: references/**/*.md
            """
        )

        payload = validate_repo.parse_yaml_string_map(frontmatter, "skills/example-skill/SKILL.md")

        self.assertEqual(
            payload,
            {
                "name": "example-skill",
                "description": "Example skill",
                "metadata": {
                    "short-description": "Short summary",
                    "docs-url": "https://example.com/skills/example-skill",
                    "path-pattern": "references/**/*.md",
                },
            },
        )
        self.assertEqual(validate_repo.ERRORS, [])

    def test_parse_yaml_string_map_strips_inline_comments_from_plain_scalars(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            name: example-skill # canonical id
            description: Example skill # summary
            metadata:
              short-description: Short summary # visible in catalog
            """
        )

        payload = validate_repo.parse_yaml_string_map(frontmatter, "skills/example-skill/SKILL.md")

        self.assertEqual(
            payload,
            {
                "name": "example-skill",
                "description": "Example skill",
                "metadata": {
                    "short-description": "Short summary",
                },
            },
        )
        self.assertEqual(validate_repo.ERRORS, [])

    def test_parse_yaml_string_map_allows_comments_after_quoted_scalars(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            name: "example-skill" # canonical id
            description: 'Example # skill' # summary
            """
        )

        payload = validate_repo.parse_yaml_string_map(frontmatter, "skills/example-skill/SKILL.md")

        self.assertEqual(
            payload,
            {
                "name": "example-skill",
                "description": "Example # skill",
            },
        )
        self.assertEqual(validate_repo.ERRORS, [])

    def test_parse_yaml_string_map_rejects_unquoted_mapping_value_marker(self) -> None:
        frontmatter = textwrap.dedent(
            """\
            name: example-skill
            description: Review loop: inspect findings
            """
        )

        payload = validate_repo.parse_yaml_string_map(frontmatter, "skills/example-skill/SKILL.md")

        self.assertIsNone(payload)
        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("must quote values containing ': '", validate_repo.ERRORS[0])

    def test_validate_frontmatter_rejects_structured_metadata(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = temp_root / "metadata-frontmatter-test"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                textwrap.dedent(
                    f"""\
                    ---
                    name: {skill_dir.name}
                    description: Example skill
                    metadata:
                      short-description: Short summary
                      docs-url: https://example.com/skills/{skill_dir.name}
                    ---
                    # {skill_dir.name}
                    """
                ),
                encoding="utf-8",
            )

            validate_repo.validate_frontmatter(skill_dir, skill_md)

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("Unsupported canonical frontmatter keys", validate_repo.ERRORS[0])
        self.assertIn("metadata", validate_repo.ERRORS[0])

    def test_validate_frontmatter_accepts_inline_comments(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = temp_root / "inline-comment-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                textwrap.dedent(
                    f"""\
                    ---
                    name: {skill_dir.name} # canonical id
                    description: Example skill # summary
                    ---
                    # {skill_dir.name}
                    """
                ),
                encoding="utf-8",
            )

            validate_repo.validate_frontmatter(skill_dir, skill_md)

        self.assertEqual(validate_repo.ERRORS, [])

    def test_validate_frontmatter_rejects_allowed_tools(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "allowed-tools-skill",
                """\
                name: allowed-tools-skill
                description: Example skill
                allowed-tools: Bash(git:*) Bash(jq:*) Read
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("allowed-tools", validate_repo.ERRORS[0])

    def test_validate_frontmatter_rejects_empty_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "empty-allowed-tools-skill",
                """\
                name: empty-allowed-tools-skill
                description: Example skill
                allowed-tools: "   "
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("allowed-tools", validate_repo.ERRORS[0])

    def test_validate_frontmatter_accepts_standard_description_limit(self) -> None:
        description = "a" * 1024

        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "long-description-skill",
                f"""\
                name: long-description-skill
                description: {description}
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(validate_repo.ERRORS, [])

    def test_validate_frontmatter_rejects_description_over_standard_limit(self) -> None:
        description = "a" * 1025

        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "too-long-description-skill",
                f"""\
                name: too-long-description-skill
                description: {description}
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("Description is too long", validate_repo.ERRORS[0])

    def test_validate_frontmatter_rejects_compatibility(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "compatibility-limit-skill",
                f"""\
                name: compatibility-limit-skill
                description: Example skill
                compatibility: {"a" * 500}
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("compatibility", validate_repo.ERRORS[0])

    def test_validate_frontmatter_rejects_trailing_hyphen_names(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "trailing-hyphen-skill",
                """\
                name: trailing-hyphen-skill-
                description: Example skill
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("Invalid skill name", validate_repo.ERRORS[0])

    def test_validate_frontmatter_rejects_consecutive_hyphen_names(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            skill_dir = self.write_skill_with_frontmatter(
                temp_root,
                "consecutive-hyphen-skill",
                """\
                name: consecutive--hyphen-skill
                description: Example skill
                """,
            )

            validate_repo.validate_frontmatter(skill_dir, skill_dir / "SKILL.md")

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("Invalid skill name", validate_repo.ERRORS[0])


class ValidateRepoEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_repo.ERRORS.clear()

    def tearDown(self) -> None:
        validate_repo.ERRORS.clear()

    def test_invalid_trigger_ids_do_not_satisfy_minimum_counts(self) -> None:
        scenarios = (
            ("empty", "", "must be a non-empty string or integer"),
            ("boolean", True, "must be a non-empty string or integer"),
            ("path-like", "../positive-2", "must be a safe path segment"),
            ("duplicate", "positive-1", "Duplicate trigger eval id"),
        )

        for label, invalid_id, expected_error in scenarios:
            with self.subTest(label=label):
                validate_repo.ERRORS.clear()
                with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
                    skill_dir = Path(temp_dir) / "trigger-count-skill"
                    evals_dir = Path(temp_dir) / "eval-suite"
                    evals_dir.mkdir()
                    (evals_dir / "evals.json").write_text(
                        json.dumps(
                            {
                                "skill_name": skill_dir.name,
                                "trigger_evals": [
                                    {
                                        "id": "positive-1",
                                        "query": "use the skill",
                                        "should_trigger": True,
                                    },
                                    {
                                        "id": invalid_id,
                                        "query": "use the skill again",
                                        "should_trigger": True,
                                    },
                                    {
                                        "id": "negative-1",
                                        "query": "translate this",
                                        "should_trigger": False,
                                    },
                                    {
                                        "id": "negative-2",
                                        "query": "check the weather",
                                        "should_trigger": False,
                                    },
                                ],
                                "behavior_evals": [
                                    {
                                        "id": "basic",
                                        "prompt": "use the skill",
                                        "expected_behavior": "Uses the skill.",
                                        "fixtures": [],
                                        "checks": ["Uses the skill workflow"],
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )

                    validate_repo.validate_evals(skill_dir, evals_dir)

                self.assertTrue(
                    any(expected_error in error for error in validate_repo.ERRORS),
                    validate_repo.ERRORS,
                )
                self.assertTrue(
                    any(
                        "Need at least 2 positive trigger evals" in error
                        for error in validate_repo.ERRORS
                    ),
                    validate_repo.ERRORS,
                )
                self.assertFalse(
                    any(
                        "Need at least 2 negative trigger evals" in error
                        for error in validate_repo.ERRORS
                    ),
                    validate_repo.ERRORS,
                )

    def test_fixture_paths_must_match_evaluator_safety_rules(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            skill_dir = Path(temp_dir) / "fixture-path-skill"
            evals_dir = Path(temp_dir) / "eval-suite"
            evals_dir.mkdir()
            (evals_dir / "evals.json").write_text(
                json.dumps(
                    {
                        "skill_name": skill_dir.name,
                        "trigger_evals": [
                            {"id": 1, "query": "one", "should_trigger": True},
                            {"id": 2, "query": "two", "should_trigger": True},
                            {"id": 3, "query": "three", "should_trigger": False},
                            {"id": 4, "query": "four", "should_trigger": False},
                        ],
                        "behavior_evals": [
                            {
                                "id": 1,
                                "prompt": "demo",
                                "expected_behavior": "works",
                                "fixtures": ["../state", "/tmp/state", ".", "evals.json"],
                                "checks": ["result exists"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            validate_repo.validate_evals(skill_dir, evals_dir)

        path_errors = [error for error in validate_repo.ERRORS if "must be eval-relative" in error]
        self.assertEqual(
            len(path_errors),
            4,
            validate_repo.ERRORS,
        )

    def test_fixture_references_must_resolve(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            skill_dir = Path(temp_dir) / "fixture-resolution-skill"
            evals_dir = Path(temp_dir) / "eval-suite"
            evals_dir.mkdir()
            (evals_dir / "evals.json").write_text(
                json.dumps(
                    {
                        "skill_name": skill_dir.name,
                        "trigger_evals": [
                            {"id": 1, "query": "one", "should_trigger": True},
                            {"id": 2, "query": "two", "should_trigger": True},
                            {"id": 3, "query": "three", "should_trigger": False},
                            {"id": 4, "query": "four", "should_trigger": False},
                        ],
                        "behavior_evals": [
                            {
                                "id": 1,
                                "prompt": "demo",
                                "expected_behavior": "works",
                                "fixtures": ["missing-scenario"],
                                "checks": ["result exists"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            validate_repo.validate_evals(skill_dir, evals_dir)

        self.assertTrue(
            any("fixture is unresolved" in error for error in validate_repo.ERRORS),
            validate_repo.ERRORS,
        )


class ValidateRepoSkillLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_repo.ERRORS.clear()

    def tearDown(self) -> None:
        validate_repo.ERRORS.clear()

    def test_validate_skills_root_accepts_flat_skills_with_external_evals(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            skills_dir = Path(temp_dir) / "skills"
            skill_dir = skills_dir / "example-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: example-skill\ndescription: Example skill\n---\n",
                encoding="utf-8",
            )
            evals_dir = Path(temp_dir) / "evals"
            (evals_dir / "example-skill").mkdir(parents=True)

            with (
                mock.patch.object(validate_repo, "SKILLS_DIR", skills_dir),
                mock.patch.object(validate_repo, "EVALS_DIR", evals_dir),
                mock.patch.object(validate_repo, "validate_skill_contract"),
                mock.patch.object(validate_repo, "validate_evals"),
            ):
                valid_skills = validate_repo.validate_skills_root()

        self.assertEqual(valid_skills, ["example-skill"])
        self.assertEqual(validate_repo.ERRORS, [])


class ValidateRepoPortabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_repo.ERRORS.clear()

    def tearDown(self) -> None:
        validate_repo.ERRORS.clear()

    def test_validate_portability_rejects_sibling_skill_refs(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            sibling_dir = temp_root / "commit"
            sibling_dir.mkdir()
            skill_dir = temp_root / "sibling-ref-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: sibling-ref-skill
                    description: Example skill
                    ---
                    # Example

                    Run ../commit/scripts/helper.py before continuing.
                    """
                ),
                encoding="utf-8",
            )

            validate_repo.validate_portability_patterns(skill_dir)

        self.assertEqual(len(validate_repo.ERRORS), 1)
        self.assertIn("Forbidden sibling-skill path reference", validate_repo.ERRORS[0])

    def test_validate_portability_rejects_generic_parent_refs(self) -> None:
        with tempfile.TemporaryDirectory(dir=validate_repo.SKILLS_DIR) as temp_dir:
            skill_dir = Path(temp_dir)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: repo-parent-ref-skill
                    description: Example skill
                    ---
                    # Example

                    Read ../README.md, run ../scripts/check-skills.sh, or use
                    ../../scripts/check-skills.sh before using this skill.
                    """
                ),
                encoding="utf-8",
            )

            validate_repo.validate_portability_patterns(skill_dir)

        self.assertEqual(len(validate_repo.ERRORS), 3)
        self.assertTrue(
            all(
                error.startswith("Forbidden parent-path reference")
                for error in validate_repo.ERRORS
            )
        )

    def test_validate_portability_rejects_raw_prefix_bypass(self) -> None:
        with tempfile.TemporaryDirectory(dir=validate_repo.SKILLS_DIR) as temp_dir:
            skill_dir = Path(temp_dir)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: raw-prefix-bypass-skill
                    description: Example skill
                    ---
                    # Example

                    Do not allow ../raw//../scripts/check-skills.sh or
                    ../../raw/source.md/../scripts/check-skills.sh.
                    """
                ),
                encoding="utf-8",
            )

            validate_repo.validate_portability_patterns(skill_dir)

        self.assertEqual(len(validate_repo.ERRORS), 2)
        self.assertIn(
            "../raw//../scripts/check-skills.sh",
            validate_repo.ERRORS[0],
        )
        self.assertIn(
            "../../raw/source.md/../scripts/check-skills.sh",
            validate_repo.ERRORS[1],
        )


if __name__ == "__main__":
    unittest.main()
