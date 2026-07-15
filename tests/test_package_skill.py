import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_DIR / "scripts" / "package_skill.py"
SPEC = importlib.util.spec_from_file_location("package_skill", SCRIPT_PATH)
assert SPEC is not None
package_skill = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(package_skill)


class PackageSkillTests(unittest.TestCase):
    def write_skill(self, root: Path, name: str = "demo") -> Path:
        skill = root / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use for demo work.\n---\n",
            encoding="utf-8",
        )
        return skill

    def test_invalid_source_does_not_remove_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self.write_skill(root / "source-root")
            outside = root / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (source / "leak.txt").symlink_to(outside)
            destination = root / "installed"
            destination.mkdir()
            sentinel = destination / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")

            with contextlib.redirect_stderr(io.StringIO()):
                status = package_skill.main([str(source), str(destination)])

            self.assertEqual(status, 1)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_destination_symlink_is_replaced_without_removing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self.write_skill(root / "source-root")
            target = root / "target"
            target.mkdir()
            sentinel = target / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            destination = root / "installed"
            destination.symlink_to(target, target_is_directory=True)

            status = package_skill.main([str(source), str(destination)])

            self.assertEqual(status, 0)
            self.assertFalse(destination.is_symlink())
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")

    def test_source_and_destination_may_not_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self.write_skill(root)

            with contextlib.redirect_stderr(io.StringIO()):
                status = package_skill.main([str(source), str(source / "package")])

            self.assertEqual(status, 1)
            self.assertFalse((source / "package").exists())

    def test_destination_parent_symlink_may_not_bypass_overlap_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self.write_skill(root / "source-root")
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(source, target_is_directory=True)
            destination = linked_parent / "package"

            with contextlib.redirect_stderr(io.StringIO()):
                status = package_skill.main([str(source), str(destination)])

            self.assertEqual(status, 1)
            self.assertFalse((source / "package").exists())


if __name__ == "__main__":
    unittest.main()
