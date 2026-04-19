import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_DIR / "scripts" / "validate_repo.py"
SPEC = importlib.util.spec_from_file_location("validate_repo", MODULE_PATH)
validate_repo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_repo)


class ValidateRepoFrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_repo.ERRORS.clear()

    def tearDown(self) -> None:
        validate_repo.ERRORS.clear()

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

    def test_validate_frontmatter_accepts_structured_metadata(self) -> None:
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

        self.assertEqual(validate_repo.ERRORS, [])

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


class ValidateRepoPortabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        validate_repo.ERRORS.clear()

    def tearDown(self) -> None:
        validate_repo.ERRORS.clear()

    def test_validate_portability_allows_llm_wiki_output_raw_refs(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            skill_dir = Path(temp_dir) / "llm-wiki"
            references_dir = skill_dir / "references"
            fixture_dir = skill_dir / "evals" / "fixtures" / "wiki" / "sources"
            references_dir.mkdir(parents=True)
            fixture_dir.mkdir(parents=True)
            (skill_dir / "evals").mkdir(exist_ok=True)

            (references_dir / "wiki-contract.md").write_text(
                textwrap.dedent(
                    """\
                    # Contract

                    Use normal markdown links for raw file paths:

                    [raw transcript](../../raw/2026-04-19-interview.md)

                    From nested wiki pages, use `../../raw/source.md`. From
                    top-level wiki files, use `../raw/source.md`.

                    raw_path: ../../raw/example-source.md
                    """
                ),
                encoding="utf-8",
            )
            (fixture_dir / "source-example.md").write_text(
                "raw_path: ../../raw/example-source.md\n",
                encoding="utf-8",
            )
            (skill_dir / "evals" / "evals.json").write_text(
                '{"expected": "Links with `../../raw/example-source.md`."}\n',
                encoding="utf-8",
            )

            validate_repo.validate_portability_patterns(skill_dir)

        self.assertEqual(validate_repo.ERRORS, [])

    def test_allowed_output_parent_paths_are_limited_to_raw_links(self) -> None:
        self.assertTrue(validate_repo.is_allowed_output_parent_path("../raw/source.md"))
        self.assertTrue(
            validate_repo.is_allowed_output_parent_path("../../raw/assets/image.png")
        )
        self.assertFalse(validate_repo.is_allowed_output_parent_path("../assets/image.png"))
        self.assertFalse(
            validate_repo.is_allowed_output_parent_path("../../scripts/check-skills.sh")
        )
        self.assertFalse(validate_repo.is_allowed_output_parent_path("../raw"))
        self.assertFalse(validate_repo.is_allowed_output_parent_path("../raw/"))
        self.assertFalse(
            validate_repo.is_allowed_output_parent_path(
                "../raw//../scripts/check-skills.sh"
            )
        )
        self.assertFalse(
            validate_repo.is_allowed_output_parent_path("../raw/source name.md")
        )
        self.assertFalse(validate_repo.is_allowed_output_parent_path("../../../raw/source.md"))
        self.assertFalse(validate_repo.is_allowed_output_parent_path("../../raw/../README.md"))

    def test_validate_portability_rejects_sibling_skill_refs(self) -> None:
        with tempfile.TemporaryDirectory(dir=validate_repo.SKILLS_DIR) as temp_dir:
            skill_dir = Path(temp_dir)
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

    def test_validate_portability_rejects_raw_refs_outside_output_contexts(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            temp_root = Path(temp_dir)
            other_skill_dir = temp_root / "other-skill"
            other_skill_dir.mkdir()
            (other_skill_dir / "SKILL.md").write_text(
                "See [raw](../raw/source.md) and raw_path: ../raw/source.md.\n",
                encoding="utf-8",
            )

            validate_repo.validate_portability_patterns(other_skill_dir)

        self.assertEqual(len(validate_repo.ERRORS), 2)
        self.assertTrue(
            all(
                error.startswith("Forbidden parent-path reference")
                for error in validate_repo.ERRORS
            )
        )

    def test_validate_portability_rejects_command_like_raw_refs(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_DIR) as temp_dir:
            skill_dir = Path(temp_dir) / "llm-wiki"
            references_dir = skill_dir / "references"
            references_dir.mkdir(parents=True)
            (references_dir / "wiki-contract.md").write_text(
                textwrap.dedent(
                    """\
                    # Contract

                    Do not treat bash ../raw/secret.sh as a generated output link.
                    Do not treat `bash ../raw/secret.sh` as one either.
                    """
                ),
                encoding="utf-8",
            )

            validate_repo.validate_portability_patterns(skill_dir)

        self.assertEqual(len(validate_repo.ERRORS), 2)
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
