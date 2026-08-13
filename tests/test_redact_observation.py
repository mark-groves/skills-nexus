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
SCRIPT_PATH = REPO_DIR / "scripts" / "redact_observation.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))
SPEC = importlib.util.spec_from_file_location("redact_observation", SCRIPT_PATH)
assert SPEC is not None
redact_observation_cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(redact_observation_cli)

from skill_observation import (  # noqa: E402
    ObservationError,
    build_observation,
    load_draft,
    load_stored_observation,
    write_observation,
)
from skill_triage import (  # noqa: E402
    redact_observation,
    redact_text,
    write_redacted_observation,
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


class ObservationRedactionTests(unittest.TestCase):
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

    def stored_observation(
        self, root: Path, draft_payload: dict[str, object] | None = None
    ) -> dict:
        skill = self.write_skill(root)
        draft = load_draft(self.write_draft(root, draft_payload or valid_draft()))
        return build_observation(draft, skill_dir=skill, repo_root=root)

    def test_redact_text_replaces_secrets_and_pii_deterministically(self) -> None:
        text = (
            "Contact ada@example.com from /home/ada/work. "
            "Key AKIAIOSFODNN7EXAMPLE and token ghp_" + ("a" * 36) + "."
        )
        first, first_counts = redact_text(text)
        second, second_counts = redact_text(text)

        self.assertEqual(first, second)
        self.assertEqual(first_counts, second_counts)
        self.assertEqual(first_counts["email"], 1)
        self.assertEqual(first_counts["home_path"], 1)
        self.assertEqual(first_counts["aws_access_key"], 1)
        self.assertEqual(first_counts["github_token"], 1)
        self.assertIn("[REDACTED:EMAIL]", first)
        self.assertIn("[REDACTED:HOME_PATH]", first)
        self.assertIn("[REDACTED:AWS_ACCESS_KEY]", first)
        self.assertIn("[REDACTED:GITHUB_TOKEN]", first)
        self.assertNotIn("ada@example.com", first)
        self.assertNotIn("/home/ada", first)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", first)

    def test_redact_text_is_idempotent_on_placeholders(self) -> None:
        text = "email ada@example.com password=hunter2"
        redacted, _counts = redact_text(text)
        again, again_counts = redact_text(redacted)

        self.assertEqual(redacted, again)
        self.assertEqual(again_counts, {})

    def test_redact_text_keeps_instruction_pointers_and_prose(self) -> None:
        text = "See SKILL.md#Validate before grouping the commit."
        redacted, counts = redact_text(text)
        self.assertEqual(redacted, text)
        self.assertEqual(counts, {})

    def test_redact_text_covers_pem_labeled_secret_ssn_and_phone(self) -> None:
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n"
            "password=hunter2 ssn 123-45-6789 call (555) 123-4567 "
            "jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.signature-value"
        )
        redacted, counts = redact_text(text)
        self.assertEqual(counts["private_key"], 1)
        self.assertEqual(counts["labeled_secret"], 1)
        self.assertEqual(counts["ssn"], 1)
        self.assertEqual(counts["phone"], 1)
        self.assertEqual(counts["jwt"], 1)
        self.assertIn("[REDACTED:PRIVATE_KEY]", redacted)
        self.assertIn("password=[REDACTED:SECRET]", redacted)
        self.assertIn("[REDACTED:SSN]", redacted)
        self.assertIn("[REDACTED:PHONE]", redacted)
        self.assertIn("[REDACTED:JWT]", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("123-45-6789", redacted)

    def test_redact_observation_scrubs_free_text_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = valid_draft()
            payload["task"]["summary"] = (  # type: ignore[index]
                "User ada@example.com failed in /Users/ada/src."
            )
            payload["signals"][0]["evidence_excerpt"] = (  # type: ignore[index]
                "Authorization Bearer super-secret-token-value"
            )
            payload["suggested_change"] = "Ask ada@example.com to retry."
            observation = self.stored_observation(root, payload)
            redacted, counts = redact_observation(observation)

        self.assertEqual(redacted["observation_id"], observation["observation_id"])
        self.assertEqual(redacted["trust"], "untrusted")
        self.assertEqual(redacted["skill"], observation["skill"])
        self.assertEqual(redacted["outcome"], observation["outcome"])
        self.assertEqual(redacted["runtime"], observation["runtime"])
        self.assertEqual(redacted["signals"][0]["kind"], "instruction_confusion")
        self.assertEqual(redacted["signals"][0]["instruction_ref"], "SKILL.md#Validate")
        self.assertIn("[REDACTED:EMAIL]", redacted["task"]["summary"])
        self.assertIn("[REDACTED:HOME_PATH]", redacted["task"]["summary"])
        self.assertIn("[REDACTED:BEARER]", redacted["signals"][0]["evidence_excerpt"])
        self.assertIn("[REDACTED:EMAIL]", redacted["suggested_change"])
        self.assertGreaterEqual(counts["email"], 2)
        self.assertIn("home_path", counts)
        self.assertIn("bearer", counts)

    def test_write_redacted_observation_leaves_inbox_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            before = inbox.read_bytes()
            redacted, _counts = redact_observation(observation)
            destination = write_redacted_observation(redacted, root / "triage")
            again = write_redacted_observation(redacted, root / "triage")
            loaded = load_stored_observation(destination)
            inbox_after = inbox.read_bytes()
            mode = stat.S_IMODE(destination.stat().st_mode)
            destination_parent = destination.parent.name
            destination_name = destination.name

        self.assertEqual(inbox_after, before)
        self.assertEqual(destination, again)
        self.assertEqual(mode, 0o600)
        self.assertEqual(destination_parent, "demo")
        self.assertEqual(destination_name, f"{observation['observation_id']}.json")
        self.assertEqual(loaded["observation_id"], observation["observation_id"])
        self.assertEqual(loaded["trust"], "untrusted")

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
                write_redacted_observation(observation, linked)

    def test_write_rejects_absolute_skill_id_and_leaves_output_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "triage"
            output_root.mkdir()
            outside = root / "outside"
            observation = {
                "observation_id": "obs-escape",
                "skill": {"id": str(outside)},
            }
            with self.assertRaisesRegex(ObservationError, "safe path segment"):
                write_redacted_observation(observation, output_root)
            self.assertFalse(outside.exists())
            self.assertEqual(list(output_root.rglob("*")), [])

    def test_write_rejects_traversal_skill_id_and_observation_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_root = root / "triage"
            output_root.mkdir()
            with self.assertRaisesRegex(ObservationError, "safe path segment"):
                write_redacted_observation(
                    {"observation_id": "safe", "skill": {"id": "../escape"}},
                    output_root,
                )
            with self.assertRaisesRegex(ObservationError, "safe path segment"):
                write_redacted_observation(
                    {"observation_id": "nested/id", "skill": {"id": "demo"}},
                    output_root,
                )
            self.assertEqual(list(output_root.rglob("*")), [])

    def test_cli_redacts_stored_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = valid_draft()
            payload["task"]["summary"] = "Ping ada@example.com"  # type: ignore[index]
            observation = self.stored_observation(root, payload)
            inbox = write_observation(observation, root / "inbox")
            before = inbox.read_bytes()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = redact_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            records = list((root / "triage" / "demo").glob("*.json"))
            loaded = load_stored_observation(records[0])
            inbox_after = inbox.read_bytes()
            printed = stdout.getvalue().strip()

        self.assertEqual(status, 0)
        self.assertEqual(len(records), 1)
        self.assertEqual(inbox_after, before)
        self.assertIn("[REDACTED:EMAIL]", loaded["task"]["summary"])
        self.assertEqual(printed, str(records[0]))

    def test_cli_rejects_draft_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draft_path = self.write_draft(root, valid_draft())
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = redact_observation_cli.main(
                    [
                        "--input",
                        str(draft_path),
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            triage_exists = (root / "triage").exists()
            error_text = stderr.getvalue()

        self.assertEqual(status, 1)
        self.assertIn("missing", error_text)
        self.assertFalse(triage_exists)


if __name__ == "__main__":
    unittest.main()
