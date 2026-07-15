import contextlib
import importlib.util
import io
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_DIR / "scripts" / "record_observation.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))
SPEC = importlib.util.spec_from_file_location("record_observation", SCRIPT_PATH)
assert SPEC is not None
record_observation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(record_observation)

from skill_observation import (  # noqa: E402
    ACTIVATIONS,
    CONFIDENCE,
    INVOCATIONS,
    OUTCOMES,
    SIGNAL_KINDS,
    SOURCE_KINDS,
    ObservationError,
    build_observation,
    load_draft,
    write_observation,
)


def valid_draft() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": {"kind": "agent", "external_run_id": "run-123"},
        "runtime": {
            "harness": "codex",
            "harness_version": "1.2.3",
            "model": "example-model",
            "invocation": "automatic",
            "activation": "activated",
        },
        "task": {
            "category": "prepare-commit",
            "summary": "Prepared an intentional commit from a mixed worktree.",
        },
        "outcome": "partial",
        "signals": [
            {
                "kind": "instruction_confusion",
                "observation": "The agent reconsidered the stopping condition twice.",
                "instruction_ref": "SKILL.md#Validate",
                "evidence_excerpt": "Validation ran twice before the agent stopped.",
                "diagnosis": "The stopping condition was ambiguous.",
                "diagnosis_confidence": "high",
            }
        ],
        "suggested_change": "Clarify the stopping condition.",
    }


class ObservationContractTests(unittest.TestCase):
    def write_draft(self, root: Path, payload: object) -> Path:
        path = root / "draft.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_skill(self, root: Path, name: str = "demo") -> Path:
        skill = root / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use for demo work.\n---\n\n# Demo\n",
            encoding="utf-8",
        )
        return skill

    def test_load_draft_accepts_exact_bounded_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draft = load_draft(self.write_draft(root, valid_draft()))

        self.assertEqual(draft["outcome"], "partial")
        self.assertEqual(draft["signals"][0]["kind"], "instruction_confusion")

    def test_published_schema_matches_validator_contract(self) -> None:
        schema = json.loads(
            (REPO_DIR / "schemas" / "skill-observation-draft-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        properties = schema["properties"]
        signal = properties["signals"]["items"]

        self.assertEqual(set(schema["required"]), set(properties))
        self.assertEqual(properties["schema_version"]["const"], 1)
        self.assertEqual(set(properties["source"]["properties"]["kind"]["enum"]), SOURCE_KINDS)
        self.assertEqual(
            set(properties["runtime"]["properties"]["invocation"]["enum"]), INVOCATIONS
        )
        self.assertEqual(
            set(properties["runtime"]["properties"]["activation"]["enum"]), ACTIVATIONS
        )
        self.assertEqual(set(properties["outcome"]["enum"]), OUTCOMES)
        self.assertEqual(set(signal["properties"]["kind"]["enum"]), SIGNAL_KINDS)
        self.assertEqual(
            set(signal["properties"]["diagnosis_confidence"]["enum"]),
            CONFIDENCE | {None},
        )

    def test_load_draft_rejects_arbitrary_fields(self) -> None:
        payload = valid_draft()
        payload["raw_transcript"] = "untrusted content"
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ObservationError, "unexpected raw_transcript"):
                load_draft(self.write_draft(Path(temp_dir), payload))

    def test_load_draft_rejects_invalid_enums_and_control_characters(self) -> None:
        payload = valid_draft()
        payload["outcome"] = "mostly-okay"
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ObservationError, "outcome must be one of"):
                load_draft(self.write_draft(Path(temp_dir), payload))

        payload = valid_draft()
        payload["schema_version"] = 2
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ObservationError, "schema_version must be 1"):
                load_draft(self.write_draft(Path(temp_dir), payload))

        payload = valid_draft()
        payload["task"]["summary"] = "unsafe\x00summary"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ObservationError, "control characters"):
                load_draft(self.write_draft(Path(temp_dir), payload))

    def test_build_and_write_adds_provenance_and_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = self.write_skill(root)
            draft = load_draft(self.write_draft(root, valid_draft()))
            observation = build_observation(draft, skill_dir=skill, repo_root=root)
            destination = write_observation(observation, root / ".skill-feedback" / "inbox")

            stored = json.loads(destination.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(destination.stat().st_mode)

        self.assertEqual(stored["schema_version"], 1)
        self.assertEqual(stored["trust"], "untrusted")
        self.assertEqual(stored["skill"]["id"], "demo")
        self.assertEqual(len(stored["skill"]["runtime_digest_sha256"]), 64)
        self.assertEqual(mode, 0o600)

    def test_runtime_digest_excludes_repository_only_evals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = self.write_skill(root)
            draft = load_draft(self.write_draft(root, valid_draft()))
            before = build_observation(draft, skill_dir=skill, repo_root=root)

            (skill / "evals").mkdir()
            (skill / "evals" / "evals.json").write_text("{}", encoding="utf-8")
            after = build_observation(draft, skill_dir=skill, repo_root=root)

        self.assertEqual(
            before["skill"]["runtime_digest_sha256"],
            after["skill"]["runtime_digest_sha256"],
        )

    def test_write_rejects_symlinked_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            observation = {
                "observation_id": "safe-id",
                "skill": {"id": "demo"},
            }
            with self.assertRaisesRegex(ObservationError, "may not contain symlinks"):
                write_observation(observation, linked)

    def test_write_rejects_symlinked_output_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)
            observation = {
                "observation_id": "safe-id",
                "skill": {"id": "demo"},
            }
            with self.assertRaisesRegex(ObservationError, "may not contain symlinks"):
                write_observation(observation, linked / "inbox")

    def test_cli_records_valid_draft_for_known_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_skill(root)
            draft_path = self.write_draft(root, valid_draft())
            output = root / "feedback"

            with contextlib.redirect_stdout(io.StringIO()):
                status = record_observation.main(
                    [
                        "--repo-root",
                        str(root),
                        "--skill",
                        "demo",
                        "--input",
                        str(draft_path),
                        "--output-root",
                        str(output),
                    ]
                )

            records = list((output / "demo").glob("*.json"))

        self.assertEqual(status, 0)
        self.assertEqual(len(records), 1)

    def test_cli_rejects_skill_outside_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside"
            outside.mkdir()
            (outside / "SKILL.md").write_text(
                "---\nname: outside\ndescription: Use for outside work.\n---\n",
                encoding="utf-8",
            )
            draft_path = self.write_draft(root, valid_draft())

            with contextlib.redirect_stderr(io.StringIO()):
                status = record_observation.main(
                    [
                        "--repo-root",
                        str(root),
                        "--skill",
                        str(outside),
                        "--input",
                        str(draft_path),
                        "--output-root",
                        str(root / "feedback"),
                    ]
                )

        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
