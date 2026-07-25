import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_DIR / "scripts" / "eval_skills.py"
sys.path.insert(0, str(REPO_DIR / "scripts"))
SPEC = importlib.util.spec_from_file_location("eval_skills", SCRIPT_PATH)
assert SPEC is not None
eval_skills = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(eval_skills)

from skill_eval.codex_runner import CodexRunner, _event_summary, _scrub  # noqa: E402
from skill_eval.core import (  # noqa: E402
    BehaviorCase,
    EvalError,
    EvaluationCondition,
    TriggerCase,
    candidate_evaluation_conditions,
    default_evaluation_conditions,
    discover_repository_skills,
    git_observations,
    initialize_fixture_repository,
    load_eval_spec,
    materialize_fixtures,
    resolve_candidate_skill,
    run_fixture_setups,
    runtime_skill_copy,
    snapshot_workspace,
    summarize_behavior_results,
    summarize_trigger_results,
)


class EvalCoreTests(unittest.TestCase):
    def test_default_conditions_are_immutable_ordered_and_digest_the_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill = Path(temp_dir) / "source-package"
            skill.mkdir()
            (skill / "SKILL.md").write_text("# Demo\n", encoding="utf-8")

            conditions = default_evaluation_conditions(skill)

            self.assertEqual(tuple(condition.id for condition in conditions), ("skill", "baseline"))
            self.assertEqual(
                tuple(condition.display_label for condition in conditions),
                ("Skill", "Baseline"),
            )
            self.assertEqual(conditions[0].runtime_skill_dir, skill.resolve())
            self.assertIsNotNone(conditions[0].runtime_digest_sha256)
            self.assertEqual(conditions[0].installation_name, "source-package")
            self.assertIsNone(conditions[1].runtime_skill_dir)
            self.assertIsNone(conditions[1].runtime_digest_sha256)
            self.assertEqual(conditions[1].installation_name, "source-package")
            with self.assertRaises(FrozenInstanceError):
                conditions[0].id = "changed"  # type: ignore[misc]

    def test_candidate_conditions_share_one_logical_install_slot_and_separate_digests(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "demo"
            candidate = root / "candidate-package"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("current\n", encoding="utf-8")
            (candidate / "SKILL.md").write_text("candidate\n", encoding="utf-8")

            conditions = candidate_evaluation_conditions(current, candidate)

            self.assertEqual(
                tuple(condition.id for condition in conditions),
                ("skill", "baseline", "candidate"),
            )
            self.assertEqual(
                tuple(condition.display_label for condition in conditions),
                ("Current", "Baseline", "Candidate"),
            )
            self.assertEqual(
                {condition.installation_name for condition in conditions},
                {"demo"},
            )
            self.assertNotEqual(
                conditions[0].runtime_digest_sha256,
                conditions[2].runtime_digest_sha256,
            )

    def test_candidate_resolution_accepts_repo_relative_and_absolute_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            candidate = repo / "working" / "next-demo"
            candidate.mkdir(parents=True)
            (candidate / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for improved demo tasks.\n---\n\n# Demo\n",
                encoding="utf-8",
            )

            relative = resolve_candidate_skill(repo, Path("working/next-demo"), "demo")
            absolute = resolve_candidate_skill(repo, candidate, "demo")

            self.assertEqual(relative, candidate.resolve())
            self.assertEqual(absolute, candidate.resolve())

    def test_candidate_resolution_rejects_missing_malformed_and_mismatched_packages(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)

            with self.assertRaisesRegex(EvalError, "does not exist"):
                resolve_candidate_skill(repo, Path("missing"), "demo")

            malformed = repo / "malformed"
            malformed.mkdir()
            (malformed / "SKILL.md").write_text("name: demo\n", encoding="utf-8")
            with self.assertRaisesRegex(EvalError, "must start with YAML frontmatter"):
                resolve_candidate_skill(repo, Path("malformed"), "demo")

            mismatched = repo / "mismatched"
            mismatched.mkdir()
            (mismatched / "SKILL.md").write_text(
                "---\nname: other\ndescription: Use for other tasks.\n---\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "logical skill identity mismatch"):
                resolve_candidate_skill(repo, Path("mismatched"), "demo")

            extra_metadata = repo / "extra-metadata"
            extra_metadata.mkdir()
            (extra_metadata / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for demo tasks.\nallowed-tools: Bash\n---\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "unsupported canonical frontmatter"):
                resolve_candidate_skill(repo, Path("extra-metadata"), "demo")

            missing_reference = repo / "missing-reference"
            missing_reference.mkdir()
            (missing_reference / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for demo tasks.\n---\n\n"
                "Read `references/missing.md` before acting.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "missing local path"):
                resolve_candidate_skill(repo, Path("missing-reference"), "demo")

            nonportable = repo / "working" / "nonportable"
            nonportable.mkdir(parents=True)
            (nonportable / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for demo tasks.\n---\n\n"
                "Read ~/.codex/skills directly.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "not portable"):
                resolve_candidate_skill(repo, Path("working/nonportable"), "demo")

    def test_candidate_validation_failure_precedes_runner_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            skill = repo / "skills" / "demo"
            candidate = repo / "candidate"
            skill.mkdir(parents=True)
            candidate.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for demo tasks.\n---\n",
                encoding="utf-8",
            )
            (candidate / "SKILL.md").write_text(
                "---\nname: other\ndescription: Use for other tasks.\n---\n",
                encoding="utf-8",
            )

            with (
                mock.patch.object(eval_skills, "CodexRunner") as runner,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                status = eval_skills.main(
                    [
                        "--repo-root",
                        str(repo),
                        "--skill",
                        "demo",
                        "--candidate",
                        str(candidate),
                        "--plan",
                    ]
                )

            self.assertEqual(status, 1)
            runner.assert_not_called()

    def test_behavior_summary_uses_condition_ids_instead_of_fixed_keys(self) -> None:
        conditions = (
            EvaluationCondition("current", None, None, "demo", "Current"),
            EvaluationCondition("control", None, None, "demo", "Control"),
        )
        run = {
            "status": "completed",
            "duration_seconds": 1.0,
            "usage": {"input_tokens": 2, "output_tokens": 1},
            "tool_calls": 1,
        }
        results = [
            {
                "case_id": "case",
                "repeat": 1,
                "current_run": {**run, "activated": True},
                "control_run": {**run, "activated": False},
                "grades": {
                    "current": [{"passed": True}],
                    "control": [{"passed": False}],
                },
                "judge": {"status": "completed"},
            }
        ]

        summary = summarize_behavior_results(results, conditions)

        self.assertEqual(summary["current"]["pass_rate"], 1.0)
        self.assertEqual(summary["control"]["pass_rate"], 0.0)
        self.assertEqual(summary["absolute_lift"], 1.0)
        self.assertEqual(summary["paired_checks"]["skill_wins"], 1)
        self.assertEqual(summary["cases"][0]["current_status"], "completed")

    def test_behavior_summary_rejects_condition_ids_that_collide_with_output_keys(
        self,
    ) -> None:
        conditions = (
            EvaluationCondition("efficiency", None, None, "demo", "Current"),
            EvaluationCondition("control", None, None, "demo", "Control"),
        )

        with self.assertRaisesRegex(EvalError, "reserved behavior summary keys: efficiency"):
            summarize_behavior_results([], conditions)

    def test_behavior_summary_reports_all_candidate_pairwise_comparisons(self) -> None:
        conditions = (
            EvaluationCondition("skill", None, None, "demo", "Current"),
            EvaluationCondition("baseline", None, None, "demo", "Baseline"),
            EvaluationCondition("candidate", None, None, "demo", "Candidate"),
        )
        run = {
            "status": "completed",
            "duration_seconds": 1.0,
            "usage": {},
            "tool_calls": 0,
            "activated": False,
        }
        summary = summarize_behavior_results(
            [
                {
                    "case_id": "case",
                    "repeat": 1,
                    "skill_run": run,
                    "baseline_run": run,
                    "candidate_run": run,
                    "grades": {
                        "skill": [{"passed": True}],
                        "baseline": [{"passed": False}],
                        "candidate": [{"passed": False}],
                    },
                    "judge": {"status": "completed"},
                }
            ],
            conditions,
        )

        self.assertEqual(
            set(summary["comparisons"]),
            {
                "current_vs_baseline",
                "candidate_vs_baseline",
                "candidate_vs_current",
            },
        )
        self.assertEqual(summary["absolute_lift"], 1.0)
        self.assertEqual(
            summary["comparisons"]["candidate_vs_current"]["absolute_lift"],
            -1.0,
        )
        self.assertEqual(
            summary["comparisons"]["candidate_vs_current"]["paired_checks"]["right_wins"],
            1,
        )

    def test_duplicate_case_filters_are_rejected(self) -> None:
        case = TriggerCase("1", "demo", True)

        with self.assertRaisesRegex(EvalError, "Duplicate trigger case id"):
            eval_skills._select_cases((case,), ["1", "1"], None, kind="trigger")

    def test_eval_ids_must_be_safe_path_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            evals_root = Path(temp_dir) / "evals"
            eval_path = evals_root / "demo" / "evals.json"
            eval_path.parent.mkdir(parents=True)
            for unsafe_id in ("../escape", "/tmp/escape", r"..\escape", ".", ".."):
                with self.subTest(unsafe_id=unsafe_id):
                    eval_path.write_text(
                        json.dumps(
                            {
                                "skill_name": "demo",
                                "trigger_evals": [
                                    {
                                        "id": unsafe_id,
                                        "query": "demo",
                                        "should_trigger": True,
                                    }
                                ],
                                "behavior_evals": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(EvalError, "safe path segment"):
                        load_eval_spec(skill_dir, evals_root)

    def test_empty_fixture_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            evals_root = Path(temp_dir) / "evals"
            eval_path = evals_root / "demo" / "evals.json"
            eval_path.parent.mkdir(parents=True)
            eval_path.write_text(
                json.dumps(
                    {
                        "skill_name": "demo",
                        "trigger_evals": [],
                        "behavior_evals": [
                            {
                                "id": 1,
                                "prompt": "demo",
                                "expected_behavior": "works",
                                "fixtures": ["   "],
                                "checks": ["result exists"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(EvalError, "non-empty strings"):
                load_eval_spec(skill_dir, evals_root)

    def test_broad_fixture_references_cannot_select_eval_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "evals" / "skill"
            workspace = root / "workspace"
            eval_dir.mkdir(parents=True)
            (eval_dir / "evals.json").write_text("{}", encoding="utf-8")
            workspace.mkdir()

            for fixture in (".", "evals.json", "fixtures"):
                with self.subTest(fixture=fixture):
                    with self.assertRaisesRegex(EvalError, "eval ground truth"):
                        materialize_fixtures(
                            eval_dir, (fixture,), workspace, allow_setup_scripts=False
                        )

    def test_peer_skill_call_does_not_count_as_target_activation(self) -> None:
        events = [
            {
                "type": "item.completed",
                "item": {"type": "skill_call", "name": "peer"},
            }
        ]

        summary = _event_summary(
            events,
            activation_marker="skills/target/SKILL.md",
            activation_name="target",
        )

        self.assertFalse(summary["activated"])

    def test_repository_discovery_excludes_skills_inside_eval_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            canonical = repo / "skills" / "canonical"
            peer = repo / "skills" / "peer"
            embedded = repo / "evals" / "canonical" / "fixtures" / "embedded"
            nested = repo / "skills" / "category" / "nested"
            canonical.mkdir(parents=True)
            embedded.mkdir(parents=True)
            peer.mkdir(parents=True)
            nested.mkdir(parents=True)
            (canonical / "SKILL.md").write_text("canonical", encoding="utf-8")
            (embedded / "SKILL.md").write_text("embedded", encoding="utf-8")
            (peer / "SKILL.md").write_text("peer", encoding="utf-8")
            (nested / "SKILL.md").write_text("nested", encoding="utf-8")

            discovered = discover_repository_skills(repo)

            self.assertEqual(set(discovered), {canonical.resolve(), peer.resolve()})
            self.assertNotIn(embedded.resolve(), discovered)
            self.assertNotIn(nested.resolve(), discovered)

    def test_runtime_skill_copy_preserves_canonical_runtime_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            (source / "references").mkdir(parents=True)
            (source / "working").mkdir()
            (source / "evals" / "fixtures").mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: source\ndescription: Example skill\n---\n\n# Skill\n",
                encoding="utf-8",
            )
            (source / "references" / "guide.md").write_text("guide", encoding="utf-8")
            (source / "working" / "scratch.txt").write_text("scratch", encoding="utf-8")
            (source / "evals" / "evals.json").write_text("{}", encoding="utf-8")
            (source / "evals" / "fixtures" / "secret.txt").write_text("withheld", encoding="utf-8")

            destination = root / "installed"
            runtime_skill_copy(source, destination)

            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "references" / "guide.md").is_file())
            self.assertFalse((destination / "working").exists())
            self.assertFalse((destination / "evals").exists())
            self.assertEqual(
                (destination / "SKILL.md").read_text(encoding="utf-8"),
                (source / "SKILL.md").read_text(encoding="utf-8"),
            )

    def test_runtime_skill_copy_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            (source / "references").mkdir(parents=True)
            (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            outside = root / "answer.md"
            outside.write_text("external\n", encoding="utf-8")
            (source / "references" / "answer.md").symlink_to(outside)

            destination = root / "installed"
            with self.assertRaisesRegex(EvalError, "may not contain symlinks"):
                runtime_skill_copy(source, destination)

            self.assertFalse(destination.exists())

    def test_markdown_recipe_withholds_expected_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "evals" / "skill"
            workspace = root / "workspace"
            eval_dir.mkdir(parents=True)
            workspace.mkdir()
            (eval_dir / "state.md").write_text(
                "# State\n\nRepository has a dirty file.\n\n## Expected behavior\nCommit it.\n",
                encoding="utf-8",
            )

            records, scripts = materialize_fixtures(
                eval_dir, ("state",), workspace, allow_setup_scripts=True
            )

            copied = (workspace / ".eval" / "fixtures" / "state.md").read_text(encoding="utf-8")
            self.assertIn("dirty file", copied)
            self.assertNotIn("Commit it", copied)
            self.assertEqual(records[0]["mode"], "description_only")
            self.assertEqual(scripts, [])

    def test_markdown_recipe_rejects_symlink_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "evals" / "skill"
            workspace = root / "workspace"
            outside = root / "outside.md"
            eval_dir.mkdir(parents=True)
            workspace.mkdir()
            outside.write_text("host-local content\n", encoding="utf-8")
            (eval_dir / "state.md").symlink_to(outside)

            with self.assertRaisesRegex(EvalError, "may not be symlinks"):
                materialize_fixtures(eval_dir, ("state",), workspace, allow_setup_scripts=False)

    def test_top_level_fixture_file_is_copied_to_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "evals" / "skill"
            workspace = root / "workspace"
            (eval_dir / "fixtures").mkdir(parents=True)
            workspace.mkdir()
            (eval_dir / "fixtures" / "input.txt").write_text("input\n", encoding="utf-8")

            records, scripts = materialize_fixtures(
                eval_dir, ("input.txt",), workspace, allow_setup_scripts=False
            )

            self.assertEqual((workspace / "input.txt").read_text(encoding="utf-8"), "input\n")
            self.assertFalse((workspace / "fixtures").exists())
            self.assertEqual(records[0]["copied"], ["input.txt"])
            self.assertEqual(scripts, [])

    def test_markdown_recipe_withholds_plain_expected_behavior_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "evals" / "skill"
            workspace = root / "workspace"
            eval_dir.mkdir(parents=True)
            workspace.mkdir()
            (eval_dir / "state.md").write_text(
                "# State\n\nRepository has a dirty file.\n\n"
                "Expected behavior:\nCommit it with the expected subject.\n",
                encoding="utf-8",
            )

            materialize_fixtures(eval_dir, ("state",), workspace, allow_setup_scripts=True)

            copied = (workspace / ".eval" / "fixtures" / "state.md").read_text(encoding="utf-8")
            self.assertIn("dirty file", copied)
            self.assertNotIn("Expected behavior", copied)
            self.assertNotIn("expected subject", copied)

    def test_only_fixture_root_setup_script_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            eval_dir = root / "evals" / "skill"
            fixture = eval_dir / "fixtures" / "repository"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / "setup.sh").write_text("true\n", encoding="utf-8")
            (fixture / "scripts" / "setup.sh").write_text("repository content\n", encoding="utf-8")

            enabled_workspace = root / "enabled"
            enabled_workspace.mkdir()
            enabled_records, enabled_scripts = materialize_fixtures(
                eval_dir, ("repository",), enabled_workspace, allow_setup_scripts=True
            )
            self.assertEqual(enabled_scripts, [fixture / "setup.sh"])
            self.assertTrue((enabled_workspace / "scripts" / "setup.sh").is_file())
            self.assertIn("scripts/setup.sh", enabled_records[0]["copied"])

            disabled_workspace = root / "disabled"
            disabled_workspace.mkdir()
            disabled_records, disabled_scripts = materialize_fixtures(
                eval_dir, ("repository",), disabled_workspace, allow_setup_scripts=False
            )
            self.assertEqual(disabled_scripts, [])
            self.assertEqual(disabled_records[0]["status"], "degraded")
            self.assertTrue((disabled_workspace / "scripts" / "setup.sh").is_file())
            self.assertFalse((disabled_workspace / "setup.sh").exists())

    def test_repository_init_failure_degrades_fixture_fidelity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            failed = mock.Mock(returncode=1, stderr="git unavailable")
            with mock.patch("skill_eval.core.subprocess.run", return_value=failed):
                repository = initialize_fixture_repository(workspace)

            self.assertFalse(repository["ok"])
            self.assertEqual(eval_skills._fixture_fidelity([], [], repository), "setup-failed")

    def test_evidence_scrubbing_preserves_skill_name_vocabulary(self) -> None:
        value = "git commit -m 'fix' in /tmp/eval/workspace"

        scrubbed = _scrub(value, {"/tmp/eval": "<RUN_ROOT>"})

        self.assertEqual(scrubbed, "git commit -m 'fix' in <RUN_ROOT>/workspace")

    def test_codex_home_is_created_without_persistent_auth_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "run"
            skill = root / "skill"
            run_dir.mkdir()
            skill.mkdir()
            auth = root / "auth.json"
            auth.write_text("{}", encoding="utf-8")
            runner = object.__new__(CodexRunner)
            runner.auth_source = auth
            runner.peer_skills = ()

            home = runner._prepare_home(condition=None, include_peers=False)
            try:
                self.assertNotIn(run_dir, home.parents)
                self.assertNotIn(root, home.parents)
                self.assertFalse((home / "auth.json").exists())
            finally:
                shutil.rmtree(home, ignore_errors=True)

    def test_codex_home_installs_selected_runtime_by_logical_name_with_peer_parity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = root / "candidate-source"
            peer = root / "peer"
            runtime.mkdir()
            peer.mkdir()
            (runtime / "SKILL.md").write_text("# Candidate\n", encoding="utf-8")
            (peer / "SKILL.md").write_text("# Peer\n", encoding="utf-8")
            condition = EvaluationCondition(
                id="current",
                runtime_skill_dir=runtime,
                runtime_digest_sha256="digest",
                installation_name="demo",
                display_label="Current",
            )
            baseline = EvaluationCondition(
                id="control",
                runtime_skill_dir=None,
                runtime_digest_sha256=None,
                installation_name="demo",
                display_label="Control",
            )
            runner = object.__new__(CodexRunner)
            runner.peer_skills = (peer,)

            current_home = runner._prepare_home(condition=condition, include_peers=True)
            control_home = runner._prepare_home(condition=baseline, include_peers=True)
            try:
                self.assertTrue(
                    (current_home / ".agents" / "skills" / "demo" / "SKILL.md").is_file()
                )
                self.assertFalse((current_home / ".agents" / "skills" / runtime.name).exists())
                self.assertFalse((control_home / ".agents" / "skills" / "demo").exists())
                for home in (current_home, control_home):
                    self.assertTrue((home / ".agents" / "skills" / "peer" / "SKILL.md").is_file())
            finally:
                shutil.rmtree(current_home, ignore_errors=True)
                shutil.rmtree(control_home, ignore_errors=True)

    def test_codex_api_key_is_wrapped_as_ephemeral_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            codex_home = root / "empty-codex-home"
            skill.mkdir()
            codex_home.mkdir()
            (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {"CODEX_HOME": str(codex_home), "CODEX_API_KEY": "ci-test-key"},
            ):
                runner = CodexRunner(
                    conditions=default_evaluation_conditions(skill),
                    codex_binary="/bin/true",
                    model=None,
                    judge_model=None,
                    timeout_seconds=30,
                    sandbox="read-only",
                )

            self.assertEqual(
                json.loads(runner.auth_payload),
                {"auth_mode": "apikey", "OPENAI_API_KEY": "ci-test-key"},
            )

    def test_combined_skill_read_keeps_non_skill_command_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "run" / "workspace"
            workspace.mkdir(parents=True)
            events_path = root / "events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": (
                                "cat /tmp/private/.agents/skills/commit/SKILL.md "
                                "&& git status && pytest"
                            ),
                            "exit_code": 0,
                            "status": "completed",
                            "aggregated_output": "private instructions\nchecks passed\n",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runner = object.__new__(CodexRunner)
            runner.runtime_skill_names = {"commit"}
            run = {
                "events_path": str(events_path),
                "workspace": str(workspace),
                "runtime_home": "/tmp/private",
                "final_response": "Created a commit.",
                "status": "completed",
                "artifact_delta": {"created": [], "modified": [], "deleted": []},
                "git": {"available": True},
                "duration_seconds": 1.0,
                "usage": {},
                "tool_calls": 1,
            }

            bundle = runner._evidence_bundle(run)

            self.assertEqual(len(bundle["commands"]), 1)
            command = bundle["commands"][0]
            self.assertIn("git status && pytest", command["command"])
            self.assertNotIn("skills/commit/SKILL.md", command["command"])
            self.assertEqual(
                command["output"],
                "<REDACTED: command output included skill instructions>",
            )
            self.assertEqual(bundle["final_response"], "Created a commit.")

    def test_artifact_skill_instruction_copy_is_redacted(self) -> None:
        runner = object.__new__(CodexRunner)
        runner.runtime_skill_names = {"commit"}
        runner.runtime_instruction_texts = (
            "# Commit workflow\nAlways inspect the repository before creating a commit.\n",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            events_path = root / "events.jsonl"
            events_path.write_text("", encoding="utf-8")
            run = {
                "events_path": str(events_path),
                "workspace": str(workspace),
                "runtime_home": "/tmp/private",
                "final_response": "Done.",
                "status": "completed",
                "artifact_delta": {
                    "created": [
                        {
                            "path": "copied.md",
                            "text": (
                                "# Commit workflow\n"
                                "Always inspect the repository before creating a commit.\n"
                            ),
                        }
                    ],
                    "modified": [],
                    "deleted": [],
                },
                "git": {"available": False},
                "duration_seconds": 1.0,
                "usage": {},
                "tool_calls": 1,
            }

            bundle = runner._evidence_bundle(run)

        artifact = bundle["artifact_delta"]["created"][0]
        self.assertTrue(artifact["text_redacted"])
        self.assertNotIn("Always inspect", json.dumps(bundle))

    def test_task_workspace_is_preserved_after_external_execution(self) -> None:
        runner = object.__new__(CodexRunner)
        runner.sandbox = "workspace-write"
        runner.model = None
        condition = EvaluationCondition(
            id="baseline",
            runtime_skill_dir=None,
            runtime_digest_sha256=None,
            installation_name="demo",
            display_label="Baseline",
        )
        runner.conditions = (
            EvaluationCondition(
                id="skill",
                runtime_skill_dir=Path("/unused"),
                runtime_digest_sha256="unused",
                installation_name="demo",
                display_label="Skill",
            ),
            condition,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run"

            def fake_execute(**kwargs):
                workspace = kwargs["workspace"]
                (workspace / "deliverable.bin").write_bytes(bytes(range(256)) * 64)
                return {
                    "status": "completed",
                    "events_path": str(run_dir / "events.jsonl"),
                }

            with mock.patch.object(runner, "_execute", side_effect=fake_execute):
                run = runner.run_task(
                    run_dir=run_dir,
                    workspace_template=None,
                    prompt="create a binary deliverable",
                    case_type="behavior",
                    case_id="binary",
                    repeat=1,
                    condition=condition,
                )

            preserved = Path(run["workspace"])
            executed = Path(run["execution_workspace"])
            self.assertEqual((preserved / "deliverable.bin").read_bytes(), bytes(range(256)) * 64)
            self.assertFalse(executed.exists())

    def test_task_rejects_condition_object_that_differs_from_configuration(self) -> None:
        configured = EvaluationCondition(
            id="skill",
            runtime_skill_dir=Path("/configured"),
            runtime_digest_sha256="configured-digest",
            installation_name="demo",
            display_label="Skill",
        )
        supplied = EvaluationCondition(
            id="skill",
            runtime_skill_dir=Path("/different"),
            runtime_digest_sha256="different-digest",
            installation_name="demo",
            display_label="Skill",
        )
        runner = object.__new__(CodexRunner)
        runner.conditions = (
            configured,
            EvaluationCondition(
                id="baseline",
                runtime_skill_dir=None,
                runtime_digest_sha256=None,
                installation_name="demo",
                display_label="Baseline",
            ),
        )

        with self.assertRaisesRegex(EvalError, "exactly match"):
            runner.run_task(
                run_dir=Path("/unused"),
                workspace_template=None,
                prompt="unused",
                case_type="trigger",
                case_id="condition",
                repeat=1,
                condition=supplied,
            )

    def test_grading_validates_condition_keys_before_allocating_workspace(self) -> None:
        conditions = (
            EvaluationCondition("current", None, None, "demo", "Current"),
            EvaluationCondition("control", None, None, "demo", "Control"),
        )
        runner = object.__new__(CodexRunner)
        runner.conditions = conditions
        behavior_case = BehaviorCase(
            id="case",
            prompt="demo",
            expected_behavior="works",
            fixtures=(),
            checks=("works",),
        )

        with mock.patch("skill_eval.codex_runner.tempfile.mkdtemp") as make_temp:
            with self.assertRaisesRegex(EvalError, "must match the configured conditions"):
                runner.grade_pair(
                    grade_dir=Path("/unused"),
                    behavior_case=behavior_case,
                    repeat=1,
                    runs_by_condition={"current": {}},
                )

        make_temp.assert_not_called()

    def test_shell_expanded_skill_read_redacts_command_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "run" / "workspace"
            workspace.mkdir(parents=True)
            events_path = root / "events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "cat $(find /tmp/private/.agents/skills -name SKILL.md)",
                            "exit_code": 0,
                            "status": "completed",
                            "aggregated_output": "private skill instructions\n",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runner = object.__new__(CodexRunner)
            runner.runtime_skill_names = {"commit"}
            run = {
                "events_path": str(events_path),
                "workspace": str(workspace),
                "runtime_home": "/tmp/private",
                "final_response": "Done.",
                "status": "completed",
                "artifact_delta": {"created": [], "modified": [], "deleted": []},
                "git": {"available": True},
                "duration_seconds": 1.0,
                "usage": {},
                "tool_calls": 1,
            }

            bundle = runner._evidence_bundle(run)

            self.assertEqual(
                bundle["commands"][0]["output"],
                "<REDACTED: command output included skill instructions>",
            )
            self.assertNotIn("private skill instructions", json.dumps(bundle))

    def test_workspace_skill_fixture_output_is_not_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "run" / "workspace"
            workspace.mkdir(parents=True)
            events_path = root / "events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "cat skills/pdf-processing/SKILL.md",
                            "exit_code": 0,
                            "status": "completed",
                            "aggregated_output": "name: pdf-processing\nportable: true\n",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runner = object.__new__(CodexRunner)
            runner.runtime_skill_names = {"skill-architect"}
            run = {
                "events_path": str(events_path),
                "workspace": str(workspace),
                "runtime_home": "/tmp/private",
                "final_response": "Audit complete.",
                "status": "completed",
                "artifact_delta": {"created": [], "modified": [], "deleted": []},
                "git": {"available": True},
                "duration_seconds": 1.0,
                "usage": {},
                "tool_calls": 1,
            }

            bundle = runner._evidence_bundle(run)

            self.assertEqual(
                bundle["commands"][0]["output"],
                "name: pdf-processing\nportable: true\n",
            )

    def test_git_observations_include_head_commit_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
            subprocess.run(
                ["git", "config", "user.email", "eval@example.invalid"],
                cwd=workspace,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Skill Eval"],
                cwd=workspace,
                check=True,
            )
            (workspace / "baseline.txt").write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "add", "baseline.txt"], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=workspace, check=True)
            (workspace / "README.md").write_text("result\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=workspace, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "result"], cwd=workspace, check=True)

            observations = git_observations(workspace)

            self.assertEqual(observations["head_commit_exit_code"], 0)
            self.assertIn("README.md", observations["head_commit"])
            self.assertNotIn("baseline.txt", observations["head_commit"])

    def test_large_text_artifact_has_bounded_head_and_tail_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            content = "BEGIN\n" + ("middle\n" * 3_000) + "END\n"
            (workspace / "catalog.drawio").write_text(content, encoding="utf-8")

            snapshot = snapshot_workspace(workspace, preview_bytes=1_000)
            record = snapshot["files"]["catalog.drawio"]

            self.assertTrue(record["text_truncated"])
            self.assertIn("BEGIN", record["text"])
            self.assertIn("END", record["text"])
            self.assertIn("bytes omitted", record["text"])
            self.assertLess(len(record["text"].encode("utf-8")), 1_100)

    def test_executable_fixture_runs_after_clean_git_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            eval_dir = root / "evals" / "skill"
            fixture = eval_dir / "fixtures" / "staged-state"
            workspace = root / "workspace"
            fixture.mkdir(parents=True)
            workspace.mkdir()
            (fixture / "README.md").write_text("baseline\n", encoding="utf-8")
            (fixture / "setup.sh").write_text(
                "printf 'changed\\n' > \"$EVAL_WORKSPACE/README.md\"\n"
                'git -C "$EVAL_WORKSPACE" add README.md\n',
                encoding="utf-8",
            )

            records, scripts = materialize_fixtures(
                eval_dir, ("staged-state",), workspace, allow_setup_scripts=True
            )
            repository = initialize_fixture_repository(workspace)
            setups = run_fixture_setups(scripts, workspace, skill)

            self.assertTrue(repository["created"])
            self.assertEqual(records[0]["mode"], "executable")
            self.assertEqual(setups[0]["exit_code"], 0)
            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout, "M  README.md\n")

    def test_trigger_summary_uses_case_level_threshold(self) -> None:
        cases = (
            TriggerCase("p", "positive", True),
            TriggerCase("n", "negative", False),
        )
        runs = [
            {"case_id": "p", "status": "completed", "activated": True},
            {"case_id": "p", "status": "completed", "activated": False},
            {"case_id": "n", "status": "completed", "activated": False},
            {"case_id": "n", "status": "completed", "activated": False},
        ]

        summary = summarize_trigger_results(cases, runs, threshold=0.5)

        self.assertEqual(
            summary["confusion_matrix"],
            {"tp": 1, "fp": 0, "tn": 1, "fn": 0, "unscored": 0},
        )
        self.assertEqual(summary["balanced_accuracy"], 1.0)
        self.assertEqual(summary["run_accuracy"], 0.75)


class EvalCliIntegrationTests(unittest.TestCase):
    def _write_fake_codex(self, root: Path) -> Path:
        executable = root / "fake-codex"
        executable.write_text(
            textwrap.dedent(
                r"""
                #!/usr/bin/env python3
                import json
                import os
                import stat
                import subprocess
                import sys
                import time
                from pathlib import Path

                args = sys.argv[1:]
                if args == ["--version"]:
                    print("fake-codex 1.0")
                    raise SystemExit(0)

                home = Path(os.environ["CODEX_HOME"])
                auth_path = home / "auth.json"
                auth_is_regular = stat.S_ISREG(auth_path.stat().st_mode)
                auth = json.loads(auth_path.read_text())
                safe_external_auth = (
                    auth.get("auth_mode") == "chatgptAuthTokens"
                    and auth.get("tokens", {}).get("refresh_token") == ""
                )
                print(json.dumps({"type": "turn.started"}), flush=True)
                deadline = time.monotonic() + 2
                while auth_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                auth_removed = not auth_path.exists()
                prompt = sys.stdin.read()
                output_path = Path(args[args.index("--output-last-message") + 1])
                if "--output-schema" in args:
                    evidence = json.loads((Path.cwd() / "evidence.json").read_text())
                    candidates = []
                    labels = sorted(evidence["candidates"])
                    for candidate_number, label in enumerate(labels):
                        checks = [
                            {
                                "index": item["index"],
                                "result": "pass" if candidate_number == 0 else "fail",
                                "confidence": 0.9,
                                "evidence": f"fake evidence {label}",
                            }
                            for item in evidence["checks"]
                        ]
                        candidates.append(
                            {
                                "label": label,
                                "checks": checks,
                                "summary": f"candidate {label}",
                                "strengths": [],
                                "weaknesses": [],
                            }
                        )
                    judgment = {"candidates": candidates}
                    if len(labels) == 2:
                        judgment["comparison"] = {
                            "verdict": "A_better",
                            "rationale": "fake comparison",
                            "material_differences": [],
                        }
                    final = json.dumps(judgment)
                else:
                    skill_file = home / ".agents" / "skills" / "demo" / "SKILL.md"
                    peer_file = home / ".agents" / "skills" / "peer" / "SKILL.md"
                    skill_text = (
                        skill_file.read_text(encoding="utf-8") if skill_file.is_file() else ""
                    )
                    if "# Candidate Demo" in skill_text:
                        final = "candidate-assisted result"
                    elif skill_file.is_file():
                        final = "skill-assisted result"
                    else:
                        final = "baseline result"
                    final += f" peer={peer_file.is_file()}"
                    final += f" home_in_run={str(home).startswith(str(Path.cwd().parent))}"
                    final += f" auth_ephemeral={auth_is_regular and auth_removed}"
                    final += f" safe_external_auth={safe_external_auth}"
                    final += f" isolated_home={Path(os.environ['HOME']) == home}"
                    final += f" api_key_env={'CODEX_API_KEY' in os.environ}"
                    git_probe = subprocess.run(
                        ["git", "rev-parse", "--show-toplevel"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    parent_git = (
                        git_probe.returncode == 0
                        and Path(git_probe.stdout.strip()).resolve() != Path.cwd().resolve()
                    )
                    final += f" parent_git={parent_git}"
                    if skill_file.is_file():
                        print(
                            json.dumps(
                                {
                                    "type": "item.completed",
                                    "item": {
                                        "type": "command_execution",
                                        "command": f"sed -n 1,100p {skill_file}",
                                        "exit_code": 0,
                                        "status": "completed",
                                        "aggregated_output": "instructions",
                                    },
                                }
                            )
                        )
                output_path.write_text(final)
                print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": final}}))
                print(
                    json.dumps(
                        {
                            "type": "turn.completed",
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        }
                    )
                )
                """
            ).lstrip(),
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def test_end_to_end_generates_paired_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            skill = repo / "skills" / "demo"
            eval_dir = repo / "evals" / "demo"
            skill.mkdir(parents=True)
            eval_dir.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for demo tasks.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (eval_dir / "evals.json").write_text(
                json.dumps(
                    {
                        "skill_name": "demo",
                        "trigger_evals": [
                            {"id": 1, "query": "do a demo", "should_trigger": True},
                            {"id": 2, "query": "do something else", "should_trigger": False},
                        ],
                        "behavior_evals": [
                            {
                                "id": 1,
                                "prompt": "produce a demo result",
                                "expected_behavior": "Produces the result.",
                                "fixtures": ["input.txt"],
                                "checks": ["Final response contains a result"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (eval_dir / "fixtures").mkdir()
            (eval_dir / "fixtures" / "input.txt").write_text(
                "equivalent fixture\n",
                encoding="utf-8",
            )
            peer = repo / "skills" / "peer"
            peer.mkdir(parents=True)
            (peer / "SKILL.md").write_text(
                "---\nname: peer\ndescription: Use for peer tasks.\n---\n\n# Peer\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            codex_home = root / "user-codex"
            codex_home.mkdir()
            (codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": "test-access",
                            "refresh_token": "test-refresh",
                        },
                    }
                ),
                encoding="utf-8",
            )
            fake_codex = self._write_fake_codex(root)
            output_root = repo / ".skill-evals-test"

            plan_output = io.StringIO()
            with contextlib.redirect_stdout(plan_output):
                plan_status = eval_skills.main(
                    [
                        "--repo-root",
                        str(repo),
                        "--skill",
                        "demo",
                        "--suite",
                        "all",
                        "--plan",
                    ]
                )
            self.assertEqual(plan_status, 0)
            self.assertIn(
                "Behavior cases (maximum): 1 × 1 × (skill + baseline + paired judge) = 3 turns",
                plan_output.getvalue(),
            )
            self.assertIn("Maximum agent turns: 5", plan_output.getvalue())

            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with contextlib.redirect_stdout(io.StringIO()):
                    status = eval_skills.main(
                        [
                            "--repo-root",
                            str(repo),
                            "--skill",
                            "demo",
                            "--suite",
                            "all",
                            "--codex-binary",
                            str(fake_codex),
                            "--output-root",
                            str(output_root),
                        ]
                    )

            self.assertEqual(status, 0)
            result_paths = list(output_root.glob("demo/*/results.json"))
            self.assertEqual(len(result_paths), 1)
            result = json.loads(result_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(
                set(result),
                {
                    "schema_version",
                    "run_id",
                    "generated_at",
                    "repository",
                    "skill",
                    "runtime",
                    "config",
                    "integrity",
                    "trigger",
                    "behavior",
                    "efficacy",
                    "reproduce_command",
                },
            )
            self.assertEqual(
                set(result["skill"]),
                {
                    "name",
                    "path",
                    "eval_path",
                    "runtime_digest_sha256",
                    "eval_spec_digest_sha256",
                },
            )
            self.assertEqual(result["schema_version"], 1)
            self.assertTrue(result["integrity"]["evals_withheld"])
            self.assertTrue(result["integrity"]["peer_skill_parity"])
            self.assertEqual(result["runtime"]["codex_version"], "fake-codex 1.0")
            self.assertEqual(len(result["trigger"]["runs"]), 2)
            self.assertEqual(len(result["behavior"]["results"]), 1)
            self.assertEqual(result["behavior"]["results"][0]["judge"]["status"], "completed")
            behavior = result["behavior"]["results"][0]
            self.assertEqual(
                set(behavior),
                {
                    "case_id",
                    "repeat",
                    "prompt",
                    "expected_behavior",
                    "checks",
                    "fixture_fidelity",
                    "fixture",
                    "skill_run",
                    "baseline_run",
                    "grades",
                    "judge",
                },
            )
            self.assertEqual(set(behavior["grades"]), {"skill", "baseline"})
            self.assertEqual(
                set(behavior["judge"]["blind_map"].values()),
                {"skill", "baseline"},
            )
            self.assertTrue(all(run["condition"] == "skill" for run in result["trigger"]["runs"]))
            self.assertEqual(behavior["skill_run"]["condition"], "skill")
            self.assertEqual(behavior["baseline_run"]["condition"], "baseline")
            self.assertEqual(
                (Path(behavior["skill_run"]["workspace"]) / "input.txt").read_text(
                    encoding="utf-8"
                ),
                "equivalent fixture\n",
            )
            self.assertEqual(
                (Path(behavior["baseline_run"]["workspace"]) / "input.txt").read_text(
                    encoding="utf-8"
                ),
                "equivalent fixture\n",
            )
            self.assertIn("peer=True", behavior["skill_run"]["final_response"])
            self.assertIn("peer=True", behavior["baseline_run"]["final_response"])
            self.assertIn("home_in_run=False", behavior["skill_run"]["final_response"])
            self.assertIn("auth_ephemeral=True", behavior["skill_run"]["final_response"])
            self.assertIn("safe_external_auth=True", behavior["skill_run"]["final_response"])
            self.assertIn("isolated_home=True", behavior["skill_run"]["final_response"])
            self.assertIn("api_key_env=False", behavior["skill_run"]["final_response"])
            self.assertIn("parent_git=False", behavior["skill_run"]["final_response"])
            self.assertEqual(
                behavior["skill_run"]["command"][1:4],
                ["--ask-for-approval", "never", "exec"],
            )
            self.assertFalse(
                Path(behavior["skill_run"]["execution_workspace"]).is_relative_to(repo)
            )
            self.assertFalse(Path(behavior["skill_run"]["execution_workspace"]).exists())
            self.assertTrue(Path(behavior["skill_run"]["workspace"]).is_dir())
            self.assertTrue(Path(behavior["skill_run"]["workspace"]).is_relative_to(output_root))
            self.assertTrue((result_paths[0].parent / "report.md").is_file())
            self.assertTrue((result_paths[0].parent / "report.html").is_file())
            self.assertEqual(list(result_paths[0].parent.glob("**/codex-home")), [])
            default_report = (result_paths[0].parent / "report.md").read_text(encoding="utf-8")
            self.assertIn("| Check | Skill | Baseline | Skill evidence |", default_report)
            self.assertIn(
                "- Skill and baseline ran in fresh isolated contexts: `True`",
                default_report,
            )
            self.assertIn(
                "- Paired grading used randomized labels: `True`",
                default_report,
            )
            self.assertNotIn(
                "<h3>Skill</h3>",
                (result_paths[0].parent / "report.html").read_text(encoding="utf-8"),
            )

            candidate = repo / "skills" / "demo-next"
            candidate.mkdir()
            (candidate / "SKILL.md").write_text(
                "---\n"
                "name: demo\n"
                "description: Use for candidate demo tasks with narrower triggering.\n"
                "---\n\n"
                "# Candidate Demo\n",
                encoding="utf-8",
            )
            candidate_plan_output = io.StringIO()
            with contextlib.redirect_stdout(candidate_plan_output):
                candidate_plan_status = eval_skills.main(
                    [
                        "--repo-root",
                        str(repo),
                        "--skill",
                        "demo",
                        "--candidate",
                        "skills/demo-next",
                        "--suite",
                        "all",
                        "--plan",
                    ]
                )
            self.assertEqual(candidate_plan_status, 0)
            self.assertIn(
                "Trigger cases: 2 × 1 × (current + candidate) = 4 turns",
                candidate_plan_output.getvalue(),
            )
            self.assertIn(
                "Behavior cases (maximum): 1 × 1 × "
                "(current + baseline + candidate + condition-blind judge) = 4 turns",
                candidate_plan_output.getvalue(),
            )
            self.assertIn("Maximum agent turns: 8", candidate_plan_output.getvalue())

            candidate_output_root = repo / ".skill-evals-candidate"
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with contextlib.redirect_stdout(io.StringIO()):
                    candidate_status = eval_skills.main(
                        [
                            "--repo-root",
                            str(repo),
                            "--skill",
                            "demo",
                            "--candidate",
                            "skills/demo-next",
                            "--suite",
                            "all",
                            "--codex-binary",
                            str(fake_codex),
                            "--output-root",
                            str(candidate_output_root),
                        ]
                    )

            self.assertEqual(candidate_status, 0)
            candidate_result_path = next(candidate_output_root.glob("demo/*/results.json"))
            candidate_result = json.loads(candidate_result_path.read_text(encoding="utf-8"))
            self.assertEqual(candidate_result["schema_version"], 2)
            self.assertEqual(
                set(candidate_result)
                - {
                    "candidate",
                    "candidate_trigger",
                },
                set(result),
            )
            self.assertEqual(candidate_result["candidate"]["name"], "demo")
            self.assertEqual(candidate_result["candidate"]["path"], str(candidate.resolve()))
            self.assertNotEqual(
                candidate_result["skill"]["runtime_digest_sha256"],
                candidate_result["candidate"]["runtime_digest_sha256"],
            )
            self.assertEqual(candidate_result["runtime"]["peer_skills"], ["peer"])
            self.assertEqual(len(candidate_result["trigger"]["runs"]), 2)
            self.assertEqual(len(candidate_result["candidate_trigger"]["runs"]), 2)
            self.assertTrue(
                all(run["condition"] == "skill" for run in candidate_result["trigger"]["runs"])
            )
            self.assertTrue(
                all(
                    run["condition"] == "candidate"
                    for run in candidate_result["candidate_trigger"]["runs"]
                )
            )
            candidate_behavior = candidate_result["behavior"]["results"][0]
            self.assertEqual(
                set(candidate_behavior["grades"]),
                {"skill", "baseline", "candidate"},
            )
            self.assertEqual(
                set(candidate_behavior["judge"]["blind_map"].values()),
                {"skill", "baseline", "candidate"},
            )
            self.assertEqual(candidate_behavior["skill_run"]["condition"], "skill")
            self.assertEqual(
                candidate_behavior["candidate_run"]["condition"],
                "candidate",
            )
            self.assertEqual(
                candidate_behavior["baseline_run"]["condition"],
                "baseline",
            )
            for condition_id in ("skill", "baseline", "candidate"):
                run = candidate_behavior[f"{condition_id}_run"]
                self.assertEqual(
                    (Path(run["workspace"]) / "input.txt").read_text(encoding="utf-8"),
                    "equivalent fixture\n",
                )
                self.assertIn("peer=True", run["final_response"])
            self.assertIn(
                "skill-assisted result",
                candidate_behavior["skill_run"]["final_response"],
            )
            self.assertIn(
                "candidate-assisted result",
                candidate_behavior["candidate_run"]["final_response"],
            )
            self.assertEqual(
                set(candidate_result["behavior"]["summary"]["comparisons"]),
                {
                    "current_vs_baseline",
                    "candidate_vs_baseline",
                    "candidate_vs_current",
                },
            )
            candidate_report = (candidate_result_path.parent / "report.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("### Pairwise comparisons", candidate_report)
            self.assertIn("Candidate vs Current", candidate_report)
            self.assertIn("### Current", candidate_report)
            self.assertIn("### Candidate", candidate_report)
            candidate_reproduce = shlex.split(candidate_result["reproduce_command"])
            self.assertEqual(
                candidate_reproduce[candidate_reproduce.index("--candidate") + 1],
                "skills/demo-next",
            )

            isolated_output_root = repo / ".skill-evals-isolated"
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with contextlib.redirect_stdout(io.StringIO()):
                    isolated_status = eval_skills.main(
                        [
                            "--repo-root",
                            str(repo),
                            "--skill",
                            "demo",
                            "--suite",
                            "trigger",
                            "--skill-universe",
                            "isolated",
                            "--max-trigger-cases",
                            "2",
                            "--max-behavior-cases",
                            "1",
                            "--activation-threshold",
                            "0.75",
                            "--jobs",
                            "1",
                            "--timeout",
                            "17",
                            "--sandbox",
                            "read-only",
                            "--no-allow-fixture-scripts",
                            "--codex-binary",
                            str(fake_codex),
                            "--output-root",
                            str(isolated_output_root),
                            "--fail-under",
                            "0",
                        ]
                    )

            self.assertEqual(isolated_status, 0)
            isolated_result_path = next(isolated_output_root.glob("demo/*/results.json"))
            isolated_result = json.loads(isolated_result_path.read_text(encoding="utf-8"))
            self.assertFalse(isolated_result["integrity"]["peer_skill_parity"])
            self.assertEqual(isolated_result["runtime"]["peer_skills"], [])
            for run in isolated_result["trigger"]["runs"]:
                self.assertIn("home_in_run=False", run["final_response"])
                self.assertIn("parent_git=False", run["final_response"])
            self.assertIn(
                "Repository peer skills were held constant across conditions: `False`",
                (isolated_result_path.parent / "report.md").read_text(encoding="utf-8"),
            )
            reproduce = shlex.split(isolated_result["reproduce_command"])
            expected_options = {
                "--repo-root": str(repo),
                "--max-trigger-cases": "2",
                "--max-behavior-cases": "1",
                "--activation-threshold": "0.75",
                "--jobs": "1",
                "--timeout": "17",
                "--codex-binary": str(fake_codex),
                "--skill-universe": "isolated",
                "--sandbox": "read-only",
                "--output-root": str(isolated_output_root),
                "--fail-under": "0.0",
            }
            for option, expected_value in expected_options.items():
                self.assertIn(option, reproduce)
                self.assertEqual(reproduce[reproduce.index(option) + 1], expected_value)
            self.assertIn("--no-allow-fixture-scripts", reproduce)

            candidate_isolated_output = repo / ".skill-evals-candidate-isolated"
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                with contextlib.redirect_stdout(io.StringIO()):
                    candidate_isolated_status = eval_skills.main(
                        [
                            "--repo-root",
                            str(repo),
                            "--skill",
                            "demo",
                            "--candidate",
                            str(candidate),
                            "--suite",
                            "trigger",
                            "--skill-universe",
                            "isolated",
                            "--codex-binary",
                            str(fake_codex),
                            "--output-root",
                            str(candidate_isolated_output),
                        ]
                    )
            self.assertEqual(candidate_isolated_status, 0)
            candidate_isolated_result = json.loads(
                next(candidate_isolated_output.glob("demo/*/results.json")).read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(candidate_isolated_result["integrity"]["peer_skill_parity"])
            self.assertEqual(candidate_isolated_result["runtime"]["peer_skills"], [])
            for trigger_group in ("trigger", "candidate_trigger"):
                for run in candidate_isolated_result[trigger_group]["runs"]:
                    self.assertIn("peer=False", run["final_response"])


if __name__ == "__main__":
    unittest.main()
