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
PROMOTE_PATH = REPO_DIR / "scripts" / "promote_observation.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))

CLASSIFY_SPEC = importlib.util.spec_from_file_location("classify_observation", CLASSIFY_PATH)
assert CLASSIFY_SPEC is not None
classify_observation_cli = importlib.util.module_from_spec(CLASSIFY_SPEC)
assert CLASSIFY_SPEC.loader is not None
CLASSIFY_SPEC.loader.exec_module(classify_observation_cli)

PROMOTE_SPEC = importlib.util.spec_from_file_location("promote_observation", PROMOTE_PATH)
assert PROMOTE_SPEC is not None
promote_observation_cli = importlib.util.module_from_spec(PROMOTE_SPEC)
assert PROMOTE_SPEC.loader is not None
PROMOTE_SPEC.loader.exec_module(promote_observation_cli)

from skill_eval import load_eval_spec  # noqa: E402
from skill_observation import (  # noqa: E402
    ObservationError,
    build_observation,
    load_draft,
    write_observation,
)
from skill_review import load_case_groups  # noqa: E402
from skill_triage import (  # noqa: E402
    append_case_group_ids,
    append_eval_cases,
    build_disposition,
    close_disposition,
    load_disposition,
    next_case_id,
    promote_into_eval_suite,
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


def sample_eval_suite(skill_id: str = "demo") -> dict[str, object]:
    return {
        "skill_name": skill_id,
        "trigger_evals": [
            {"id": 1, "query": "existing trigger", "should_trigger": True},
            {"id": "note", "query": "non-numeric trigger", "should_trigger": False},
        ],
        "behavior_evals": [
            {
                "id": 1,
                "prompt": "existing prompt",
                "expected_behavior": "works",
                "fixtures": [],
                "checks": ["Uses the skill"],
            }
        ],
    }


def sample_case_groups() -> dict[str, object]:
    return {
        "schema_version": 1,
        "groups": [
            {
                "id": "development",
                "kind": "development",
                "trigger_cases": ["1", "note"],
                "behavior_cases": ["1"],
            }
        ],
    }


class ObservationPromotionTests(unittest.TestCase):
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

    def write_eval_suite(self, root: Path, skill_id: str = "demo") -> tuple[Path, Path]:
        eval_dir = root / "evals" / skill_id
        eval_dir.mkdir(parents=True)
        fixtures = eval_dir / "fixtures"
        fixtures.mkdir()
        (fixtures / "mixed-worktree").write_text("fixture\n", encoding="utf-8")
        eval_path = eval_dir / "evals.json"
        groups_path = eval_dir / "capability-case-groups.json"
        eval_path.write_text(
            json.dumps(sample_eval_suite(skill_id), indent=2) + "\n", encoding="utf-8"
        )
        groups_path.write_text(json.dumps(sample_case_groups(), indent=2) + "\n", encoding="utf-8")
        return eval_path, groups_path

    def test_next_case_id_skips_non_numeric_and_avoids_collisions(self) -> None:
        self.assertEqual(next_case_id([]), 1)
        self.assertEqual(
            next_case_id([{"id": 1}, {"id": "note"}, {"id": 3}]),
            4,
        )
        self.assertEqual(
            next_case_id([{"id": 2}, {"id": "3"}]),
            4,
        )

    def test_append_eval_cases_assigns_next_ids_and_reuses_identical_cases(self) -> None:
        payload = sample_eval_suite()
        updated, trigger_ids, behavior_ids, new_trigger_ids, new_behavior_ids = append_eval_cases(
            payload,
            trigger={"query": "new trigger", "should_trigger": True},
            behavior={
                "prompt": "new prompt",
                "expected_behavior": "fails until the stopping condition is explicit",
                "fixtures": [],
                "checks": ["States the stopping condition once"],
            },
        )

        self.assertEqual(trigger_ids, ["2"])
        self.assertEqual(behavior_ids, ["2"])
        self.assertEqual(new_trigger_ids, ["2"])
        self.assertEqual(new_behavior_ids, ["2"])
        self.assertEqual(updated["trigger_evals"][-1]["query"], "new trigger")
        self.assertEqual(updated["behavior_evals"][-1]["id"], 2)

        reused, reused_trigger, reused_behavior, reused_new_trigger, reused_new_behavior = (
            append_eval_cases(
                updated,
                trigger={"query": "new trigger", "should_trigger": True},
                behavior={
                    "prompt": "new prompt",
                    "expected_behavior": "fails until the stopping condition is explicit",
                    "fixtures": [],
                    "checks": ["States the stopping condition once"],
                },
            )
        )
        self.assertEqual(reused_trigger, ["2"])
        self.assertEqual(reused_behavior, ["2"])
        self.assertEqual(reused_new_trigger, [])
        self.assertEqual(reused_new_behavior, [])
        self.assertEqual(len(reused["trigger_evals"]), len(updated["trigger_evals"]))
        self.assertEqual(len(reused["behavior_evals"]), len(updated["behavior_evals"]))

    def test_append_case_group_ids_adds_only_unassigned_ids(self) -> None:
        updated = append_case_group_ids(
            sample_case_groups(),
            group_id="development",
            trigger_ids=["1", "4"],
            behavior_ids=["2"],
        )
        group = updated["groups"][0]
        self.assertEqual(group["trigger_cases"], ["1", "note", "4"])
        self.assertEqual(group["behavior_cases"], ["1", "2"])
        with self.assertRaisesRegex(ObservationError, "case group 'missing' was not found"):
            append_case_group_ids(
                sample_case_groups(),
                group_id="missing",
                trigger_ids=["4"],
                behavior_ids=[],
            )

    def test_promote_into_eval_suite_validates_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_path, groups_path = self.write_eval_suite(root)
            before_eval = eval_path.read_bytes()
            before_groups = groups_path.read_bytes()
            with self.assertRaisesRegex(ObservationError, "promoted eval suite is invalid"):
                promote_into_eval_suite(
                    skill_id="demo",
                    evals_root=root / "evals",
                    trigger={"query": "   ", "should_trigger": True},
                    behavior=None,
                    group_id="development",
                )
            self.assertEqual(eval_path.read_bytes(), before_eval)
            self.assertEqual(groups_path.read_bytes(), before_groups)

    def test_promote_into_eval_suite_rejects_unresolved_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_path, groups_path = self.write_eval_suite(root)
            before_eval = eval_path.read_bytes()
            before_groups = groups_path.read_bytes()
            with self.assertRaisesRegex(ObservationError, "fixture is unresolved"):
                promote_into_eval_suite(
                    skill_id="demo",
                    evals_root=root / "evals",
                    trigger=None,
                    behavior={
                        "prompt": "new prompt",
                        "expected_behavior": "new behavior",
                        "fixtures": ["missing-fixture"],
                        "checks": ["new check"],
                    },
                    group_id="development",
                )
            self.assertEqual(eval_path.read_bytes(), before_eval)
            self.assertEqual(groups_path.read_bytes(), before_groups)

    def test_cli_refuses_without_prior_classify_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            eval_path, _groups_path = self.write_eval_suite(root)
            evals_before = eval_path.read_bytes()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = promote_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--reason",
                        "Stopping condition is ambiguous.",
                        "--output-root",
                        str(root / "triage"),
                        "--evals-root",
                        str(root / "evals"),
                        "--trigger-query",
                        "clarify the stopping condition",
                        "--should-trigger",
                        "true",
                    ]
                )
            triage_exists = (root / "triage").exists()
            evals_after = eval_path.read_bytes()
            error_text = stderr.getvalue()

        self.assertEqual(status, 1)
        self.assertIn("classify it first", error_text)
        self.assertFalse(triage_exists)
        self.assertEqual(evals_after, evals_before)

    def test_cli_refuses_unpromotable_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            eval_path, _groups_path = self.write_eval_suite(root)
            evals_before = eval_path.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                classify_status = classify_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--class",
                        "environment",
                        "--output-root",
                        str(root / "triage"),
                    ]
                )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = promote_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--reason",
                        "Harness outage, not a skill defect.",
                        "--output-root",
                        str(root / "triage"),
                        "--evals-root",
                        str(root / "evals"),
                        "--trigger-query",
                        "clarify the stopping condition",
                        "--should-trigger",
                        "true",
                    ]
                )
            loaded = load_disposition(next((root / "triage" / "demo").glob("*.disposition.json")))
            evals_after = eval_path.read_bytes()
            error_text = stderr.getvalue()

        self.assertEqual(classify_status, 0)
        self.assertEqual(status, 1)
        self.assertIn("cannot be promoted", error_text)
        self.assertEqual(loaded["disposition"], "open")
        self.assertEqual(evals_after, evals_before)

    def test_cli_promotes_open_disposition_into_evals_and_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            eval_path, groups_path = self.write_eval_suite(root)
            skill_md = root / "skills" / "demo" / "SKILL.md"
            inbox_before = inbox.read_bytes()
            skill_before = skill_md.read_bytes()
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
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = promote_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--reason",
                        "Stopping condition is ambiguous and reproducible.",
                        "--output-root",
                        str(root / "triage"),
                        "--evals-root",
                        str(root / "evals"),
                        "--trigger-query",
                        "clarify the stopping condition",
                        "--should-trigger",
                        "true",
                        "--behavior-prompt",
                        "/demo stop after one validation pass",
                        "--expected-behavior",
                        "States the stopping condition once and does not revalidate.",
                        "--check",
                        "States the stopping condition once",
                        "--fixture",
                        "mixed-worktree",
                    ]
                )
            records = list((root / "triage" / "demo").glob("*.disposition.json"))
            loaded = load_disposition(records[0])
            eval_payload = json.loads(eval_path.read_text(encoding="utf-8"))
            groups_payload = json.loads(groups_path.read_text(encoding="utf-8"))
            spec = load_eval_spec(Path("demo"), root / "evals")
            load_case_groups(groups_path, spec)
            printed = stdout.getvalue().strip()
            stderr_text = stderr.getvalue()
            inbox_after = inbox.read_bytes()
            skill_after = skill_md.read_bytes()

        self.assertEqual(classify_status, 0)
        self.assertEqual(status, 0)
        self.assertEqual(printed, str(records[0]))
        self.assertEqual(loaded["disposition"], "accept")
        self.assertEqual(loaded["classification"], "instruction")
        self.assertEqual(loaded["reason"], "Stopping condition is ambiguous and reproducible.")
        self.assertEqual(eval_payload["trigger_evals"][-1]["id"], 2)
        self.assertEqual(
            eval_payload["trigger_evals"][-1]["query"], "clarify the stopping condition"
        )
        self.assertEqual(eval_payload["behavior_evals"][-1]["id"], 2)
        self.assertEqual(eval_payload["behavior_evals"][-1]["fixtures"], ["mixed-worktree"])
        self.assertEqual(groups_payload["groups"][0]["trigger_cases"][-1], "2")
        self.assertEqual(groups_payload["groups"][0]["behavior_cases"][-1], "2")
        self.assertIn("trigger 2", stderr_text)
        self.assertIn("behavior 2", stderr_text)
        self.assertEqual(inbox_after, inbox_before)
        self.assertEqual(skill_after, skill_before)

    def test_cli_refuses_already_closed_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observation = self.stored_observation(root)
            inbox = write_observation(observation, root / "inbox")
            eval_path, _groups_path = self.write_eval_suite(root)
            evals_before = eval_path.read_bytes()
            write_disposition(
                close_disposition(
                    build_disposition(observation, classification="instruction"),
                    disposition="accept",
                    reason="Already promoted.",
                ),
                root / "triage",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = promote_observation_cli.main(
                    [
                        "--input",
                        str(inbox),
                        "--reason",
                        "Try again.",
                        "--output-root",
                        str(root / "triage"),
                        "--evals-root",
                        str(root / "evals"),
                        "--trigger-query",
                        "clarify the stopping condition",
                        "--should-trigger",
                        "true",
                    ]
                )
            loaded = load_disposition(next((root / "triage" / "demo").glob("*.disposition.json")))
            evals_after = eval_path.read_bytes()
            error_text = stderr.getvalue()

        self.assertEqual(status, 1)
        self.assertIn("already has disposition accept", error_text)
        self.assertEqual(loaded["reason"], "Already promoted.")
        self.assertEqual(evals_after, evals_before)


if __name__ == "__main__":
    unittest.main()
