import contextlib
import copy
import importlib.util
import io
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_DIR / "scripts" / "classify_observation.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))
SPEC = importlib.util.spec_from_file_location("classify_observation", SCRIPT_PATH)
assert SPEC is not None
classify_observation_cli = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(classify_observation_cli)

from skill_observation import (  # noqa: E402
    ObservationError,
    build_observation,
    load_draft,
    write_observation,
)
from skill_triage import (  # noqa: E402
    CLASSIFICATIONS,
    DISPOSITIONS,
    REDACTION_RULES_VERSION,
    build_disposition,
    close_disposition,
    cluster_for,
    fingerprint_observation,
    iter_dispositions,
    load_disposition,
    redact_observation,
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


class ObservationClassificationTests(unittest.TestCase):
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

    def stored_observation(
        self, root: Path, draft_payload: dict[str, object] | None = None, *, name: str = "demo"
    ) -> dict:
        skill = self.write_skill(root, name=name)
        draft = load_draft(self.write_draft(root, draft_payload or valid_draft()))
        return build_observation(draft, skill_dir=skill, repo_root=root)

    def redacted_observation(
        self, root: Path, draft_payload: dict[str, object] | None = None, *, name: str = "demo"
    ) -> dict:
        observation = self.stored_observation(root, draft_payload, name=name)
        redacted, _counts = redact_observation(observation)
        return redacted

    def test_published_disposition_schema_matches_validator_contract(self) -> None:
        schema = json.loads(
            (REPO_DIR / "schemas" / "skill-observation-disposition-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        properties = schema["properties"]

        self.assertEqual(set(schema["required"]), set(properties))
        self.assertEqual(properties["schema_version"]["const"], 1)
        self.assertEqual(properties["redaction_rules_version"]["const"], REDACTION_RULES_VERSION)
        self.assertEqual(set(properties["classification"]["enum"]), CLASSIFICATIONS)
        self.assertEqual(set(properties["disposition"]["enum"]), DISPOSITIONS)
        self.assertEqual(properties["fingerprint"]["pattern"], "^[0-9a-f]{64}$")
        self.assertEqual(properties["observation_id"]["pattern"], "^(?!\\.\\.?$)[^/\\\\\\u0000]+$")
        self.assertEqual(properties["skill_id"]["pattern"], "^(?!\\.\\.?$)[^/\\\\\\u0000]+$")

    def test_fingerprint_is_stable_and_ignores_task_runtime_and_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self.redacted_observation(root)
            variant_draft = valid_draft()
            variant_draft["outcome"] = "failure"
            variant_draft["task"]["category"] = "git"  # type: ignore[index]
            variant_draft["task"]["summary"] = "Different user task."  # type: ignore[index]
            variant_draft["suggested_change"] = "Rewrite the whole skill."
            variant_draft["signals"][0]["evidence_excerpt"] = "Different excerpt."  # type: ignore[index]
            variant_draft["signals"][0]["diagnosis_confidence"] = "low"  # type: ignore[index]
            variant_draft["runtime"]["model"] = "other-model"  # type: ignore[index]
            variant = self.redacted_observation(root, variant_draft)

        self.assertEqual(fingerprint_observation(base), fingerprint_observation(base))
        self.assertEqual(fingerprint_observation(base), fingerprint_observation(variant))
        self.assertRegex(fingerprint_observation(base), r"^[0-9a-f]{64}$")

    def test_fingerprint_clusters_redacted_pii_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_draft = valid_draft()
            first_draft["signals"][0]["observation"] = (  # type: ignore[index]
                "User ada@example.com hit the stop condition."
            )
            second_draft = valid_draft()
            second_draft["signals"][0]["observation"] = (  # type: ignore[index]
                "User bob@example.com hit the stop condition."
            )
            first = self.redacted_observation(root, first_draft)
            second = self.redacted_observation(root, second_draft)

        self.assertIn("[REDACTED:EMAIL]", first["signals"][0]["observation"])
        self.assertEqual(first["signals"][0]["observation"], second["signals"][0]["observation"])
        self.assertEqual(fingerprint_observation(first), fingerprint_observation(second))

    def test_fingerprint_changes_with_signal_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = self.redacted_observation(root)
            other_text = valid_draft()
            other_text["signals"][0]["observation"] = "A different failure mode."  # type: ignore[index]
            other_ref = valid_draft()
            other_ref["signals"][0]["instruction_ref"] = "SKILL.md#Commit"  # type: ignore[index]
            other_skill = self.redacted_observation(root, name="other")
            changed_text = self.redacted_observation(root, other_text)
            changed_ref = self.redacted_observation(root, other_ref)

        digest = fingerprint_observation(base)
        self.assertNotEqual(digest, fingerprint_observation(changed_text))
        self.assertNotEqual(digest, fingerprint_observation(changed_ref))
        self.assertNotEqual(digest, fingerprint_observation(other_skill))

    def test_cluster_orders_by_recorded_at_then_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            redacted = self.redacted_observation(root)
            later = copy.deepcopy(redacted)
            earlier = copy.deepcopy(redacted)
            later["observation_id"] = "z-later"
            later["recorded_at"] = "2026-02-02T00:00:00+00:00"
            earlier["observation_id"] = "a-earlier"
            earlier["recorded_at"] = "2026-01-01T00:00:00+00:00"
            triage = root / "triage"
            write_disposition(build_disposition(later, classification="instruction"), triage)
            write_disposition(build_disposition(earlier, classification="script"), triage)
            cluster = cluster_for(
                fingerprint_observation(redacted),
                iter_dispositions(triage / "demo"),
            )

        self.assertEqual([item["observation_id"] for item in cluster], ["a-earlier", "z-later"])
        self.assertEqual(cluster[0]["classification"], "script")
        self.assertEqual(cluster[1]["classification"], "instruction")

    def test_build_disposition_open_has_null_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            redacted = self.redacted_observation(Path(temp_dir))

        record = build_disposition(redacted, classification="instruction")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["skill_id"], "demo")
        self.assertEqual(record["classification"], "instruction")
        self.assertEqual(record["disposition"], "open")
        self.assertIsNone(record["reason"])
        self.assertEqual(record["fingerprint"], fingerprint_observation(redacted))

    def test_build_disposition_rejects_open_reason_and_closed_without_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            redacted = self.redacted_observation(Path(temp_dir))

        with self.assertRaisesRegex(ObservationError, "open disposition reason must be null"):
            build_disposition(redacted, classification="instruction", reason="not yet")
        with self.assertRaisesRegex(ObservationError, "reject disposition reason"):
            build_disposition(redacted, classification="instruction", disposition="reject")
        with self.assertRaisesRegex(ObservationError, "classification must be one of"):
            build_disposition(redacted, classification="packaging")

    def test_write_disposition_is_idempotent_and_allows_open_reclassify(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            redacted = self.redacted_observation(root)
            triage = root / "triage"
            first = build_disposition(redacted, classification="instruction")
            destination = write_disposition(first, triage)
            again = write_disposition(first, triage)
            updated = write_disposition(
                build_disposition(redacted, classification="trigger"), triage
            )
            loaded = load_disposition(updated)
            mode = stat.S_IMODE(updated.stat().st_mode)

        self.assertEqual(destination, again)
        self.assertEqual(updated, destination)
        self.assertEqual(mode, 0o600)
        self.assertEqual(loaded["classification"], "trigger")
        self.assertEqual(loaded["disposition"], "open")
        self.assertIsNone(loaded["reason"])

    def test_write_disposition_refuses_closed_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            redacted = self.redacted_observation(root)
            triage = root / "triage"
            closed = build_disposition(
                redacted,
                classification="instruction",
                disposition="reject",
                reason="Not reproducible against the current skill.",
            )
            write_disposition(closed, triage)
            with self.assertRaisesRegex(ObservationError, "already has disposition reject"):
                write_disposition(build_disposition(redacted, classification="script"), triage)

    def test_load_disposition_rejects_extra_fields_and_open_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            redacted = self.redacted_observation(root)
            record = build_disposition(redacted, classification="instruction")
            extra = root / "extra.disposition.json"
            extra.write_text(json.dumps({**record, "duplicate_of": "x"}), encoding="utf-8")
            opened = root / "open-reason.disposition.json"
            opened.write_text(json.dumps({**record, "reason": "pending"}), encoding="utf-8")

            with self.assertRaisesRegex(ObservationError, "unexpected duplicate_of"):
                load_disposition(extra)
            with self.assertRaisesRegex(ObservationError, "open disposition reason must be null"):
                load_disposition(opened)

    def test_cli_classifies_redacted_observation_and_leaves_inbox_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = valid_draft()
            payload["signals"][0]["observation"] = (  # type: ignore[index]
                "User ada@example.com reconsidered the stopping condition."
            )
            observation = self.stored_observation(root, payload)
            inbox = write_observation(observation, root / "inbox")
            skill_md = root / "skills" / "demo" / "SKILL.md"
            skill_before = skill_md.read_bytes()
            inbox_before = inbox.read_bytes()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = classify_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--class",
                        "instruction",
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            triage_dir = root / "triage" / "demo"
            redacted_records = [
                path
                for path in triage_dir.glob("*.json")
                if not path.name.endswith(".disposition.json")
            ]
            disposition_records = list(triage_dir.glob("*.disposition.json"))
            loaded = load_disposition(disposition_records[0])
            printed = stdout.getvalue().strip()
            inbox_after = inbox.read_bytes()
            skill_after = skill_md.read_bytes()
            redacted_observation_text = json.loads(redacted_records[0].read_text())["signals"][0][
                "observation"
            ]

        self.assertEqual(status, 0)
        self.assertEqual(len(redacted_records), 1)
        self.assertEqual(len(disposition_records), 1)
        self.assertEqual(printed, str(disposition_records[0]))
        self.assertEqual(inbox_after, inbox_before)
        self.assertEqual(skill_after, skill_before)
        self.assertEqual(loaded["classification"], "instruction")
        self.assertEqual(loaded["disposition"], "open")
        self.assertIsNone(loaded["reason"])
        self.assertEqual(loaded["observation_id"], observation["observation_id"])
        self.assertIn("[REDACTED:EMAIL]", redacted_observation_text)

    def test_cli_rejects_draft_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            draft_path = self.write_draft(root, valid_draft())
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = classify_observation_cli.main(
                    [
                        "--input",
                        str(draft_path),
                        "--class",
                        "instruction",
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            triage_exists = (root / "triage").exists()
            error_text = stderr.getvalue()

        self.assertEqual(status, 1)
        self.assertIn("missing", error_text)
        self.assertFalse(triage_exists)

    def test_cli_refuses_closed_disposition_without_replacing_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            triage = root / "triage"
            with contextlib.redirect_stdout(io.StringIO()):
                classify_status = classify_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--class",
                        "instruction",
                        "--output-root",
                        str(triage),
                    ]
                )
            write_disposition(
                close_disposition(
                    load_disposition(next((triage / "demo").glob("*.disposition.json"))),
                    disposition="accept",
                    reason="Already promoted.",
                ),
                triage,
            )
            redacted_path = next(
                path
                for path in (triage / "demo").glob("*.json")
                if not path.name.endswith(".disposition.json")
            )
            redacted_before = redacted_path.read_bytes()
            rewritten = json.loads(inbox.read_text(encoding="utf-8"))
            rewritten["signals"][0]["observation"] = "A different failure mode."
            inbox.write_text(json.dumps(rewritten, indent=2) + "\n", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = classify_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--class",
                        "script",
                        "--output-root",
                        str(triage),
                    ]
                )
            loaded = load_disposition(next((triage / "demo").glob("*.disposition.json")))
            redacted_after = redacted_path.read_bytes()
            error_text = stderr.getvalue()

        self.assertEqual(classify_status, 0)
        self.assertEqual(status, 1)
        self.assertIn("already has disposition accept", error_text)
        self.assertEqual(loaded["disposition"], "accept")
        self.assertEqual(loaded["classification"], "instruction")
        self.assertEqual(redacted_after, redacted_before)


if __name__ == "__main__":
    unittest.main()
