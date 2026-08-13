import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
CLASSIFY_PATH = REPO_DIR / "scripts" / "classify_observation.py"
REJECT_PATH = REPO_DIR / "scripts" / "reject_observation.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))

CLASSIFY_SPEC = importlib.util.spec_from_file_location("classify_observation", CLASSIFY_PATH)
assert CLASSIFY_SPEC is not None
classify_observation_cli = importlib.util.module_from_spec(CLASSIFY_SPEC)
assert CLASSIFY_SPEC.loader is not None
CLASSIFY_SPEC.loader.exec_module(classify_observation_cli)

REJECT_SPEC = importlib.util.spec_from_file_location("reject_observation", REJECT_PATH)
assert REJECT_SPEC is not None
reject_observation_cli = importlib.util.module_from_spec(REJECT_SPEC)
assert REJECT_SPEC.loader is not None
REJECT_SPEC.loader.exec_module(reject_observation_cli)

from skill_observation import (  # noqa: E402
    ObservationError,
    build_observation,
    load_draft,
    write_observation,
)
from skill_triage import (  # noqa: E402
    build_disposition,
    close_disposition,
    load_disposition,
    write_disposition,
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


class ObservationRejectionTests(unittest.TestCase):
    def write_draft(self, root: Path, payload: object) -> Path:
        path = root / "draft.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_skill(self, root: Path, name: str = "demo") -> Path:
        skill = root / "skills" / name
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Use for demo work.\n---\n\n# Demo\n",
            encoding="utf-8",
        )
        return skill

    def stored_observation(self, root: Path) -> dict:
        skill = self.write_skill(root)
        draft = load_draft(self.write_draft(root, valid_draft()))
        return build_observation(draft, skill_dir=skill, repo_root=root)

    def test_close_disposition_rejects_open_and_accepts_terminal_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            observation = self.stored_observation(Path(temp_dir))
        opened = build_disposition(observation, classification="instruction")
        closed = close_disposition(
            opened, disposition="insufficient", reason="No reproducible excerpt."
        )

        self.assertEqual(closed["disposition"], "insufficient")
        self.assertEqual(closed["reason"], "No reproducible excerpt.")
        self.assertEqual(closed["classification"], "instruction")
        self.assertEqual(closed["fingerprint"], opened["fingerprint"])
        with self.assertRaisesRegex(ObservationError, "close disposition must be one of"):
            close_disposition(opened, disposition="open", reason="still open")
        with self.assertRaisesRegex(ObservationError, "already has disposition insufficient"):
            close_disposition(closed, disposition="reject", reason="again")

    def test_cli_rejects_without_prior_classify_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = reject_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--reason",
                        "Not reproducible.",
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            triage_exists = (root / "triage").exists()
            error_text = stderr.getvalue()

        self.assertEqual(status, 1)
        self.assertIn("classify it first", error_text)
        self.assertFalse(triage_exists)

    def test_cli_closes_open_disposition_without_touching_skill_or_evals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            evals = root / "evals" / "demo" / "evals.json"
            evals.parent.mkdir(parents=True)
            evals.write_text('{"trigger_evals": [], "behavior_evals": []}\n', encoding="utf-8")
            skill_md = root / "skills" / "demo" / "SKILL.md"
            inbox_before = inbox.read_bytes()
            skill_before = skill_md.read_bytes()
            evals_before = evals.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                classify_status = classify_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--class",
                        "instruction",
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = reject_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--disposition",
                        "insufficient",
                        "--reason",
                        "Excerpt does not reproduce against current skill.",
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            records = list((root / "triage" / "demo").glob("*.disposition.json"))
            loaded = load_disposition(records[0])
            printed = stdout.getvalue().strip()
            inbox_after = inbox.read_bytes()
            skill_after = skill_md.read_bytes()
            evals_after = evals.read_bytes()

        self.assertEqual(classify_status, 0)
        self.assertEqual(status, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(printed, str(records[0]))
        self.assertEqual(loaded["disposition"], "insufficient")
        self.assertEqual(loaded["classification"], "instruction")
        self.assertEqual(loaded["reason"], "Excerpt does not reproduce against current skill.")
        self.assertEqual(inbox_after, inbox_before)
        self.assertEqual(skill_after, skill_before)
        self.assertEqual(evals_after, evals_before)

    def test_cli_refuses_already_closed_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            triage = root / "triage"
            write_disposition(
                close_disposition(
                    build_disposition(observation, classification="script"),
                    disposition="reject",
                    reason="Already closed.",
                ),
                triage,
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = reject_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--reason",
                        "Try again.",
                        "--output-root",
                        str(triage),
                    ]
                )
            loaded = load_disposition(next((triage / "demo").glob("*.disposition.json")))
            error_text = stderr.getvalue()

        self.assertEqual(status, 1)
        self.assertIn("already has disposition reject", error_text)
        self.assertEqual(loaded["reason"], "Already closed.")


if __name__ == "__main__":
    unittest.main()
