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


if __name__ == "__main__":
    unittest.main()
