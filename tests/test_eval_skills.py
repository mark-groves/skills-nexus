import importlib.util
import contextlib
import io
import json
import os
import shlex
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

from skill_eval.codex_runner import _event_summary, _scrub  # noqa: E402
from skill_eval.core import (  # noqa: E402
    TriggerCase,
    discover_repository_skills,
    materialize_fixtures,
    initialize_fixture_repository,
    run_fixture_setups,
    sanitized_skill_copy,
    summarize_trigger_results,
)


class EvalCoreTests(unittest.TestCase):
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

            self.assertEqual(
                set(discovered),
                {canonical.resolve(), codex_peer.resolve()},
            )
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

            copied = (workspace / ".eval" / "fixtures" / "state.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("dirty file", copied)
            self.assertNotIn("Commit it", copied)
            self.assertEqual(records[0]["mode"], "description_only")
            self.assertEqual(scripts, [])

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

            materialize_fixtures(
                skill, ("state",), workspace, allow_setup_scripts=True
            )

            copied = (workspace / ".eval" / "fixtures" / "state.md").read_text(
                encoding="utf-8"
            )
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
            (fixture / "scripts" / "setup.sh").write_text(
                "repository content\n", encoding="utf-8"
            )

            enabled_workspace = root / "enabled"
            enabled_workspace.mkdir()
            enabled_records, enabled_scripts = materialize_fixtures(
                skill,
                ("repository",),
                enabled_workspace,
                allow_setup_scripts=True,
            )
            self.assertEqual(enabled_scripts, [fixture / "setup.sh"])
            self.assertTrue((enabled_workspace / "scripts" / "setup.sh").is_file())
            self.assertIn("scripts/setup.sh", enabled_records[0]["copied"])

            disabled_workspace = root / "disabled"
            disabled_workspace.mkdir()
            disabled_records, disabled_scripts = materialize_fixtures(
                skill,
                ("repository",),
                disabled_workspace,
                allow_setup_scripts=False,
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
            self.assertEqual(
                eval_skills._fixture_fidelity([], [], repository),
                "setup-failed",
            )

    def test_evidence_scrubbing_preserves_skill_name_vocabulary(self) -> None:
        value = "git commit -m 'fix' in /tmp/eval/workspace"

        scrubbed = _scrub(value, {"/tmp/eval": "<RUN_ROOT>"})

        self.assertEqual(scrubbed, "git commit -m 'fix' in <RUN_ROOT>/workspace")

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
                "git -C \"$EVAL_WORKSPACE\" add README.md\n",
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
                r'''
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                args = sys.argv[1:]
                if args == ["--version"]:
                    print("fake-codex 1.0")
                    raise SystemExit(0)

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
                    home = Path(os.environ["CODEX_HOME"])
                    skill_file = home / "skills" / "demo" / "SKILL.md"
                    peer_file = home / "skills" / "peer" / "SKILL.md"
                    final = "skill-assisted result" if skill_file.is_file() else "baseline result"
                    final += f" peer={peer_file.is_file()}"
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
                ''')
            .lstrip(),
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
            codex_home = root / "user-codex"
            codex_home.mkdir()
            (codex_home / "auth.json").write_text("{}", encoding="utf-8")
            fake_codex = self._write_fake_codex(root)
            output_root = root / "outputs"

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
            self.assertTrue((result_paths[0].parent / "report.md").is_file())
            self.assertTrue((result_paths[0].parent / "report.html").is_file())
            self.assertEqual(list(result_paths[0].parent.glob("**/codex-home")), [])

            isolated_output_root = root / "isolated-outputs"
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
