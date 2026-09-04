import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "scripts"))

from eval_evidence import (  # noqa: E402
    EvidenceError,
    admit,
    check_summary,
    emit,
    forbidden_vocab,
    load_admitted,
    load_ledger,
    main,
    summarize,
    validate_spec,
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def valid_spec(**overrides: object) -> dict[str, object]:
    spec: dict[str, object] = {
        "schema_version": 1,
        "run_id": "commit-draft",
        "mode": "prove-variant",
        "aggregation": "rank-all",
        "skill_name": "commit",
        "git_sha": "a7489e0",
        "case": {
            "schema_version": 1,
            "skill_name": "commit",
            "case_id": "11",
            "kind": "behavior",
            "prompt": "Draft the commit message for these changes, but do not stage or commit.",
            "expected_behavior": "Returns a conventional subject without mutating the repository.",
            "evals_json_digest_sha256": sha("evals"),
            "fixture_digest_sha256": sha("fixture"),
        },
        "variants": [
            {
                "schema_version": 1,
                "role": "current",
                "logical_skill_name": "commit",
                "digest_sha256": sha("skill"),
                "plugin_digest_sha256": sha("plugin"),
                "variant_id": "current",
            }
        ],
        "rubric": {
            "schema_version": 1,
            "criteria": [
                {
                    "id": "conventional-subject",
                    "text": "Subject uses a conventional type and stays short.",
                },
                {"id": "no-mutation", "text": "The repository is not staged or committed."},
                {"id": "motivation-body", "text": "Body explains the change when one is needed."},
            ],
        },
        "workers": [
            {
                "label": "cedar",
                "model": "cursor-grok-4.6-xhigh-fast",
                "variant_id": "current",
                "goal": "Draft a conventional commit message for the staged readme typo.",
                "prompt": "The readme has a staged typo fix. Write the commit message I should use. Do not change the repository.",
                "install_root": "project/skills/commit",
                "note_path": "project/notes/cedar.json",
            }
        ],
        "min_sample": 1,
        "judge_present": True,
        "platform_cap": False,
    }
    spec.update(overrides)
    return spec


class VocabTests(unittest.TestCase):
    def test_word_boundary_keeps_latest_and_catches_evals(self) -> None:
        self.assertEqual(forbidden_vocab("use the latest draft"), ())
        self.assertEqual(forbidden_vocab("project/evals/commit"), ("evals",))
        self.assertEqual(forbidden_vocab("spawn the candidate"), ("candidate",))


class EmitTests(unittest.TestCase):
    def test_emit_writes_task_without_sealed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            emit(valid_spec(), run_dir)
            task = json.loads((run_dir / "tasks" / "cedar.json").read_text(encoding="utf-8"))
            self.assertEqual(
                set(task),
                {"schema_version", "label", "goal", "prompt", "install_root", "note_path"},
            )
            self.assertNotIn("model", task)
            self.assertNotIn("variant_id", task)
            ledger = load_ledger(run_dir)
            self.assertEqual(ledger["workers"][0]["model"], "cursor-grok-4.6-xhigh-fast")

    def test_emit_refuses_vocab_in_prompt_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            workers = valid_spec()["workers"]
            assert isinstance(workers, list)
            prompt_spec = valid_spec()
            bad_prompt = dict(workers[0])
            bad_prompt["prompt"] = "Please compare this against the baseline."
            prompt_spec["workers"] = [bad_prompt]
            with self.assertRaises(EvidenceError):
                emit(prompt_spec, run_dir)

            path_spec = valid_spec()
            bad_path = dict(workers[0])
            bad_path["install_root"] = "project/evals/commit"
            path_spec["workers"] = [bad_path]
            with self.assertRaises(EvidenceError):
                emit(path_spec, run_dir / "other")


class AdmitAndSummarizeTests(unittest.TestCase):
    def test_admit_derives_transcript_digest_and_refuses_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            workspace = root / "work"
            transcript = workspace / "project" / "notes" / "cedar-log.txt"
            transcript.parent.mkdir(parents=True)
            transcript.write_text("fix: correct the readme typo\n", encoding="utf-8")
            emit(valid_spec(), run_dir)
            (run_dir / "returns").mkdir()
            (run_dir / "returns" / "cedar.json").write_text(
                json.dumps(
                    {
                        "label": "cedar",
                        "transcript_ref": "project/notes/cedar-log.txt",
                        "declaration": "PASS",
                        "workspace_digest_sha256": sha("workspace"),
                    }
                ),
                encoding="utf-8",
            )
            admitted = admit(run_dir, "cedar", workspace)
            self.assertEqual(admitted["admission"], "admitted")
            self.assertEqual(admitted["outputs"]["transcript_digest_sha256"], file_sha(transcript))
            self.assertEqual(admitted["pins"]["harness"], "cursor-cloud-agent")
            self.assertEqual(admitted["pins"]["model"], "cursor-grok-4.6-xhigh-fast")

            with self.assertRaises(EvidenceError):
                summarize(
                    load_ledger(run_dir),
                    load_admitted(run_dir),
                    author="Mark Groves",
                    notes="Identity rehearsal on the draft-message case.",
                    verdict="promote",
                )

            summary = summarize(
                load_ledger(run_dir),
                load_admitted(run_dir),
                author="Mark Groves",
                notes="Identity rehearsal on the draft-message case.",
                verdict="inconclusive",
            )
            self.assertEqual(summary["verdict"], "inconclusive")
            self.assertIn("no-auto-promote", summary["limits_held"])
            self.assertNotIn("sample-size", summary["limits_held"])
            self.assertNotIn("missing-judge", summary["limits_held"])
            check_summary(summary, load_ledger(run_dir), load_admitted(run_dir))

    def test_first_pass_and_missing_sample_hold_limits(self) -> None:
        spec = valid_spec(aggregation="first-pass", min_sample=2, judge_present=False)
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"
            emit(spec, run_dir)
            summary = summarize(
                load_ledger(run_dir),
                [],
                author="Mark Groves",
                notes="No admitted cells yet.",
                verdict="inconclusive",
            )
            self.assertIn("first-pass-not-comparative-green", summary["limits_held"])
            self.assertIn("sample-size", summary["limits_held"])
            self.assertIn("missing-judge", summary["limits_held"])

    def test_cli_emit_admit_summarize_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            spec_path = root / "spec.json"
            run_dir = root / "run"
            workspace = root / "work"
            out = root / "summary.json"
            spec_path.write_text(json.dumps(valid_spec()), encoding="utf-8")
            self.assertEqual(main(["emit", "--spec", str(spec_path), "--run-dir", str(run_dir)]), 0)
            transcript = workspace / "project" / "notes" / "cedar-log.txt"
            transcript.parent.mkdir(parents=True)
            transcript.write_text("docs: mention the draft path\n", encoding="utf-8")
            (run_dir / "returns").mkdir()
            (run_dir / "returns" / "cedar.json").write_text(
                json.dumps(
                    {
                        "label": "cedar",
                        "transcript_ref": "project/notes/cedar-log.txt",
                        "declaration": "ISSUES",
                        "workspace_digest_sha256": sha("workspace"),
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "admit",
                        "--run-dir",
                        str(run_dir),
                        "--label",
                        "cedar",
                        "--workspace",
                        str(workspace),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "summarize",
                        "--run-dir",
                        str(run_dir),
                        "--author",
                        "Mark Groves",
                        "--notes",
                        "CLI rehearsal.",
                        "--verdict",
                        "inconclusive",
                        "--out",
                        str(out),
                    ]
                ),
                0,
            )
            self.assertEqual(main(["check", "--run-dir", str(run_dir), "--summary", str(out)]), 0)
            self.assertEqual(
                main(
                    [
                        "summarize",
                        "--run-dir",
                        str(run_dir),
                        "--author",
                        "Mark Groves",
                        "--notes",
                        "CLI rehearsal.",
                        "--verdict",
                        "promote",
                        "--out",
                        str(root / "bad.json"),
                    ]
                ),
                1,
            )


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SpecGateTests(unittest.TestCase):
    def test_unknown_spec_key_is_rejected(self) -> None:
        spec = valid_spec()
        spec["spawn"] = True
        with self.assertRaises(EvidenceError):
            validate_spec(spec)


if __name__ == "__main__":
    unittest.main()
