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
    EvalError,
    TriggerCase,
    discover_repository_skills,
    git_observations,
    initialize_fixture_repository,
    load_eval_spec,
    materialize_fixtures,
    run_fixture_setups,
    sanitized_skill_copy,
    snapshot_workspace,
    summarize_trigger_results,
)


class EvalCoreTests(unittest.TestCase):
    def test_duplicate_case_filters_are_rejected(self) -> None:
        case = TriggerCase("1", "demo", True)

        with self.assertRaisesRegex(EvalError, "Duplicate trigger case id"):
            eval_skills._select_cases((case,), ["1", "1"], None, kind="trigger")

    def test_eval_ids_must_be_safe_path_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            eval_path = skill_dir / "evals" / "evals.json"
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
                        load_eval_spec(skill_dir)

    def test_empty_fixture_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            eval_path = skill_dir / "evals" / "evals.json"
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
                load_eval_spec(skill_dir)

    def test_broad_fixture_references_cannot_select_eval_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            workspace = root / "workspace"
            (skill / "evals").mkdir(parents=True)
            (skill / "evals" / "evals.json").write_text("{}", encoding="utf-8")
            workspace.mkdir()

            for fixture in (".", "evals"):
                with self.subTest(fixture=fixture):
                    with self.assertRaisesRegex(EvalError, "eval ground truth"):
                        materialize_fixtures(
                            skill, (fixture,), workspace, allow_setup_scripts=False
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
            canonical = repo / "skills" / "portable" / "canonical"
            embedded = canonical / "evals" / "fixtures" / "embedded"
            codex_peer = repo / "skills" / "harness" / "codex" / "codex-peer"
            other_peer = repo / "skills" / "harness" / "other" / "other-peer"
            embedded.mkdir(parents=True)
            codex_peer.mkdir(parents=True)
            other_peer.mkdir(parents=True)
            (canonical / "SKILL.md").write_text("canonical", encoding="utf-8")
            (embedded / "SKILL.md").write_text("embedded", encoding="utf-8")
            (codex_peer / "SKILL.md").write_text("codex", encoding="utf-8")
            (other_peer / "SKILL.md").write_text("other", encoding="utf-8")

            discovered = discover_repository_skills(repo)

            self.assertEqual(set(discovered), {canonical.resolve(), codex_peer.resolve()})
            self.assertNotIn(embedded.resolve(), discovered)
            self.assertNotIn(other_peer.resolve(), discovered)

    def test_sanitized_skill_copy_withholds_eval_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            (source / "evals").mkdir(parents=True)
            (source / "references").mkdir()
            (source / "SKILL.md").write_text(
                "---\n"
                "name: source\n"
                "description: Example skill\n"
                "license: Apache-2.0\n"
                "compatibility: Requires git\n"
                "metadata:\n"
                "  short-description: Example\n"
                "allowed-tools: Read Bash\n"
                "---\n\n"
                "# Skill\n",
                encoding="utf-8",
            )
            (source / "evals" / "evals.json").write_text("{}", encoding="utf-8")
            (source / "references" / "guide.md").write_text("guide", encoding="utf-8")

            destination = root / "installed"
            sanitized_skill_copy(source, destination)

            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "references" / "guide.md").is_file())
            self.assertFalse((destination / "evals").exists())
            installed = (destination / "SKILL.md").read_text(encoding="utf-8")
            frontmatter = installed.split("---", 2)[1]
            self.assertIn("name: source", frontmatter)
            self.assertIn("description: Example skill", frontmatter)
            self.assertIn("metadata:\n  short-description: Example", frontmatter)
            self.assertNotIn("license:", frontmatter)
            self.assertNotIn("compatibility:", frontmatter)
            self.assertNotIn("allowed-tools:", frontmatter)

    def test_sanitized_skill_copy_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            (source / "evals").mkdir(parents=True)
            (source / "references").mkdir()
            (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            (source / "evals" / "answer.md").write_text("secret\n", encoding="utf-8")
            (source / "references" / "answer.md").symlink_to(source / "evals" / "answer.md")

            destination = root / "installed"
            with self.assertRaisesRegex(EvalError, "may not contain symlinks"):
                sanitized_skill_copy(source, destination)

            self.assertFalse(destination.exists())

    def test_sanitized_skill_copy_ignores_eval_fixture_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            fixture = source / "evals" / "fixtures" / "scenario"
            fixture.mkdir(parents=True)
            (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            (fixture / "external").symlink_to(root / "outside")

            destination = root / "installed"
            sanitized_skill_copy(source, destination)

            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertFalse((destination / "evals").exists())

    def test_markdown_recipe_withholds_expected_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            workspace = root / "workspace"
            (skill / "evals").mkdir(parents=True)
            workspace.mkdir()
            (skill / "evals" / "state.md").write_text(
                "# State\n\nRepository has a dirty file.\n\n## Expected behavior\nCommit it.\n",
                encoding="utf-8",
            )

            records, scripts = materialize_fixtures(
                skill, ("state",), workspace, allow_setup_scripts=True
            )

            copied = (workspace / ".eval" / "fixtures" / "state.md").read_text(encoding="utf-8")
            self.assertIn("dirty file", copied)
            self.assertNotIn("Commit it", copied)
            self.assertEqual(records[0]["mode"], "description_only")
            self.assertEqual(scripts, [])

    def test_markdown_recipe_rejects_symlink_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            workspace = root / "workspace"
            outside = root / "outside.md"
            (skill / "evals").mkdir(parents=True)
            workspace.mkdir()
            outside.write_text("host-local content\n", encoding="utf-8")
            (skill / "evals" / "state.md").symlink_to(outside)

            with self.assertRaisesRegex(EvalError, "may not be symlinks"):
                materialize_fixtures(skill, ("state",), workspace, allow_setup_scripts=False)

    def test_markdown_recipe_withholds_plain_expected_behavior_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            workspace = root / "workspace"
            (skill / "evals").mkdir(parents=True)
            workspace.mkdir()
            (skill / "evals" / "state.md").write_text(
                "# State\n\nRepository has a dirty file.\n\n"
                "Expected behavior:\nCommit it with the expected subject.\n",
                encoding="utf-8",
            )

            materialize_fixtures(skill, ("state",), workspace, allow_setup_scripts=True)

            copied = (workspace / ".eval" / "fixtures" / "state.md").read_text(encoding="utf-8")
            self.assertIn("dirty file", copied)
            self.assertNotIn("Expected behavior", copied)
            self.assertNotIn("expected subject", copied)

    def test_only_fixture_root_setup_script_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill = root / "skill"
            fixture = skill / "evals" / "fixtures" / "repository"
            (fixture / "scripts").mkdir(parents=True)
            (fixture / "setup.sh").write_text("true\n", encoding="utf-8")
            (fixture / "scripts" / "setup.sh").write_text("repository content\n", encoding="utf-8")

            enabled_workspace = root / "enabled"
            enabled_workspace.mkdir()
            enabled_records, enabled_scripts = materialize_fixtures(
                skill, ("repository",), enabled_workspace, allow_setup_scripts=True
            )
            self.assertEqual(enabled_scripts, [fixture / "setup.sh"])
            self.assertTrue((enabled_workspace / "scripts" / "setup.sh").is_file())
            self.assertIn("scripts/setup.sh", enabled_records[0]["copied"])

            disabled_workspace = root / "disabled"
            disabled_workspace.mkdir()
            disabled_records, disabled_scripts = materialize_fixtures(
                skill, ("repository",), disabled_workspace, allow_setup_scripts=False
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
            runner.skill_dir = skill

            home = runner._prepare_home(with_skill=False, include_peers=False)
            try:
                self.assertNotIn(run_dir, home.parents)
                self.assertNotIn(root, home.parents)
                self.assertFalse((home / "auth.json").exists())
            finally:
                shutil.rmtree(home, ignore_errors=True)

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
                    skill_dir=skill,
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
            runner.skill_dir = Path("/skills/commit")
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
        runner.skill_dir = Path("/skills/commit")
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
                    condition="baseline",
                )

            preserved = Path(run["workspace"])
            executed = Path(run["execution_workspace"])
            self.assertEqual((preserved / "deliverable.bin").read_bytes(), bytes(range(256)) * 64)
            self.assertFalse(executed.exists())

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
            runner.skill_dir = Path("/skills/commit")
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
            runner.skill_dir = Path("/skills/skill-architect")
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
            fixture = skill / "evals" / "fixtures" / "staged-state"
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
                skill, ("staged-state",), workspace, allow_setup_scripts=True
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
                    for candidate_number, label in enumerate(("A", "B")):
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
                    final = json.dumps(
                        {
                            "candidates": candidates,
                            "comparison": {
                                "verdict": "A_better",
                                "rationale": "fake comparison",
                                "material_differences": [],
                            },
                        }
                    )
                else:
                    skill_file = home / ".agents" / "skills" / "demo" / "SKILL.md"
                    peer_file = home / ".agents" / "skills" / "peer" / "SKILL.md"
                    final = "skill-assisted result" if skill_file.is_file() else "baseline result"
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
            skill = repo / "skills" / "portable" / "demo"
            (skill / "evals").mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use for demo tasks.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (skill / "evals" / "evals.json").write_text(
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
                                "fixtures": [],
                                "checks": ["Final response contains a result"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            peer = repo / "skills" / "portable" / "peer"
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
            self.assertTrue(result["integrity"]["evals_withheld"])
            self.assertTrue(result["integrity"]["peer_skill_parity"])
            self.assertEqual(result["runtime"]["codex_version"], "fake-codex 1.0")
            self.assertEqual(len(result["trigger"]["runs"]), 2)
            self.assertEqual(len(result["behavior"]["results"]), 1)
            self.assertEqual(result["behavior"]["results"][0]["judge"]["status"], "completed")
            behavior = result["behavior"]["results"][0]
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


if __name__ == "__main__":
    unittest.main()
