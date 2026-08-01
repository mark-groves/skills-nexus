from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "probe_cursor_eval.py"
SPEC = importlib.util.spec_from_file_location("probe_cursor_eval", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


class CursorStreamTests(unittest.TestCase):
    fixtures = REPO_ROOT / "tests" / "fixtures" / "cursor-cli"

    def test_success_stream_and_existing_judgment_contract(self) -> None:
        parsed = probe.parse_cursor_stream(
            (self.fixtures / "success.ndjson").read_text(encoding="utf-8"),
            requested_model="gpt-5",
        )
        judgment = probe.validate_existing_judgment(parsed.final_response)

        self.assertEqual(parsed.session_id, "session-success")
        self.assertTrue(parsed.requested_model_matches)
        self.assertIsNone(parsed.activation)
        self.assertIsNone(parsed.token_usage)
        self.assertEqual(judgment["comparison"]["verdict"], "A_better")

    def test_unknown_events_and_fields_are_tolerated_without_zero_telemetry(self) -> None:
        parsed = probe.parse_cursor_stream(
            (self.fixtures / "unknown-event.ndjson").read_text(encoding="utf-8"),
            requested_model="gpt-5",
        )

        self.assertEqual(parsed.unknown_event_types, ("future.telemetry",))
        self.assertIsNone(parsed.token_usage)

    def test_requested_and_reported_model_mismatch_is_visible(self) -> None:
        parsed = probe.parse_cursor_stream(
            (self.fixtures / "model-mismatch.ndjson").read_text(encoding="utf-8"),
            requested_model="gpt-5",
        )

        self.assertEqual(parsed.reported_model, "GPT-5 Display Name")
        self.assertFalse(parsed.requested_model_matches)

    def test_malformed_and_partial_streams_fail_closed(self) -> None:
        for name in ("malformed.ndjson", "partial.ndjson"):
            with self.subTest(name=name), self.assertRaises(probe.ProbeError):
                probe.parse_cursor_stream((self.fixtures / name).read_text(encoding="utf-8"))

    def test_unicode_line_separator_inside_json_string_is_not_an_ndjson_boundary(self) -> None:
        events = [
            {
                "type": "system",
                "subtype": "init",
                "session_id": "unicode-session",
                "model": "gpt-5",
            },
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "before\u2028after",
                "session_id": "unicode-session",
            },
        ]
        parsed = probe.parse_cursor_stream(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
        )

        self.assertEqual(parsed.final_response, "before\u2028after")

    def test_activation_true_requires_exact_completed_skill_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill = Path(temp_dir) / ".cursor" / "skills" / "demo" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("probe\n", encoding="utf-8")
            events = [
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": "activation-session",
                    "model": "gpt-5",
                },
                {
                    "type": "tool_call",
                    "subtype": "completed",
                    "session_id": "activation-session",
                    "tool_call": {"readToolCall": {"args": {"path": str(skill)}}},
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "done",
                    "session_id": "activation-session",
                },
            ]
            parsed = probe.parse_cursor_stream(
                "\n".join(json.dumps(event) for event in events),
                expected_skill_path=skill,
            )

        self.assertTrue(parsed.activation)

    def test_relative_activation_read_resolves_from_reported_cli_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            skill = root / "home" / ".cursor" / "skills" / "demo" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("probe\n", encoding="utf-8")
            relative_skill = os.path.relpath(skill, workspace)
            events = [
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": "activation-session",
                    "model": "gpt-5",
                    "cwd": str(workspace),
                },
                {
                    "type": "tool_call",
                    "subtype": "completed",
                    "session_id": "activation-session",
                    "tool_call": {"readToolCall": {"args": {"path": relative_skill}}},
                },
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": "done",
                    "session_id": "activation-session",
                },
            ]
            parsed = probe.parse_cursor_stream(
                "\n".join(json.dumps(event) for event in events),
                expected_skill_path=skill,
            )

        self.assertTrue(parsed.activation)

    def test_judgment_omission_and_extra_fields_fail_closed(self) -> None:
        parsed = probe.parse_cursor_stream(
            (self.fixtures / "success.ndjson").read_text(encoding="utf-8")
        )
        judgment = json.loads(parsed.final_response)
        del judgment["candidates"][0]["checks"][0]["evidence"]
        with self.assertRaises(probe.ProbeError):
            probe.validate_existing_judgment(json.dumps(judgment))

    def test_fixture_command_exercises_all_sanitized_inputs(self) -> None:
        result = probe.check_fixtures(self.fixtures)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["fixtures"]["partial.ndjson"], "rejected")


class CursorProcessBoundaryTests(unittest.TestCase):
    def test_output_root_must_remain_under_gitignored_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            with self.assertRaises(probe.ProbeError):
                probe._safe_output_root(repo, repo / "tracked-output")

    def test_preflight_uses_a_fresh_home_and_reports_unauthenticated(self) -> None:
        def fake_run(command, **kwargs):
            if command[-1] == "--version":
                return "2026.07.23-test"
            if command[-1] == "--help":
                return " ".join(
                    (
                        "--print",
                        "--model",
                        "--output-format",
                        "--sandbox",
                        "--trust",
                        "--workspace",
                        "--mode",
                        "--force",
                        "--resume",
                    )
                )
            self.assertNotIn("CURSOR_API_KEY", kwargs["env"])
            return json.dumps({"isAuthenticated": False})

        with mock.patch.object(probe, "_resolved_command", return_value="/tmp/agent"):
            with mock.patch.object(probe, "_run_text", side_effect=fake_run):
                result = probe.run_preflight(command="agent")

        self.assertTrue(result["required_flags_present"])
        self.assertEqual(result["fresh_home_authentication"], "unauthenticated")

    def test_preflight_requires_complete_flag_tokens(self) -> None:
        def fake_run(command, **_kwargs):
            if command[-1] == "--version":
                return "2026.07.23-test"
            if command[-1] == "--help":
                return "--model-name --output-format --sandbox --workspace --resume"
            return json.dumps({"isAuthenticated": False})

        with mock.patch.object(probe, "_resolved_command", return_value="/tmp/agent"):
            with mock.patch.object(probe, "_run_text", side_effect=fake_run):
                result = probe.run_preflight(command="agent")

        self.assertIn("--model", result["missing_flags"])
        self.assertIn("--mode", result["missing_flags"])

    def test_live_probe_refuses_secret_bearing_parent_environment(self) -> None:
        with mock.patch.dict("os.environ", {"CURSOR_API_KEY": "never-used"}, clear=True):
            with self.assertRaises(probe.ProbeError):
                probe.run_live_probe(
                    command="agent",
                    auth_template=Path("missing"),
                    output_root=Path("unused"),
                    model="gpt-5",
                    timeout_seconds=1,
                )

    def test_live_probe_purges_dedicated_auth_on_preflight_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            auth_template = output_root / "auth-template"
            auth_template.mkdir()
            (auth_template / "auth-data.txt").write_text("fixture\n", encoding="utf-8")

            with mock.patch.dict("os.environ", {"CURSOR_API_KEY": "never-used"}, clear=True):
                with self.assertRaises(probe.ProbeError):
                    probe.run_live_probe(
                        command="agent",
                        auth_template=auth_template,
                        output_root=output_root,
                        model="gpt-5",
                        timeout_seconds=1,
                    )

            self.assertFalse(auth_template.exists())

    def test_live_probe_stops_after_cancelled_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            auth_template = output_root / "auth-template"
            auth_template.mkdir()
            cancelled = ({"process_status": "cancelled"}, None)
            with mock.patch.dict("os.environ", {}, clear=True):
                with mock.patch.object(probe, "_resolved_command", return_value="/tmp/agent"):
                    with mock.patch.object(
                        probe,
                        "_run_live_case",
                        return_value=cancelled,
                    ) as run_case:
                        with self.assertRaisesRegex(probe.ProbeError, "cancelled"):
                            probe.run_live_probe(
                                command="agent",
                                auth_template=auth_template,
                                output_root=output_root,
                                model="gpt-5",
                                timeout_seconds=1,
                            )

            self.assertEqual(run_case.call_count, 1)
            self.assertFalse(auth_template.exists())

    def test_timeout_terminates_process_group_and_records_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            home.mkdir()
            result = probe._run_streaming_process(
                ["python3", "-c", "import time; time.sleep(10)"],
                cwd=root,
                env={"PATH": "/usr/bin:/bin"},
                timeout_seconds=1,
                events_path=root / "events.jsonl",
                stderr_path=root / "stderr.log",
                secrets=(),
                credential_home=home,
                credential_paths=(),
            )

        self.assertEqual(result.status, "timeout")
        self.assertIsNotNone(result.exit_code)

    def test_partial_line_cannot_block_past_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            home.mkdir()
            result = probe._run_streaming_process(
                [
                    "python3",
                    "-c",
                    "import sys,time; sys.stdout.write('{'); sys.stdout.flush(); time.sleep(10)",
                ],
                cwd=root,
                env={"PATH": "/usr/bin:/bin"},
                timeout_seconds=1,
                events_path=root / "events.jsonl",
                stderr_path=root / "stderr.log",
                secrets=(),
                credential_home=home,
                credential_paths=(),
            )

        self.assertEqual(result.status, "timeout")

    def test_cancellation_terminates_process_group_and_records_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            home.mkdir()
            with mock.patch.object(
                probe.selectors.DefaultSelector,
                "select",
                side_effect=KeyboardInterrupt,
            ):
                result = probe._run_streaming_process(
                    ["python3", "-c", "import time; time.sleep(10)"],
                    cwd=root,
                    env={"PATH": "/usr/bin:/bin"},
                    timeout_seconds=2,
                    events_path=root / "events.jsonl",
                    stderr_path=root / "stderr.log",
                    secrets=(),
                    credential_home=home,
                    credential_paths=(),
                )

        self.assertEqual(result.status, "cancelled")
        self.assertIsNotNone(result.exit_code)

    def test_non_zero_exit_is_distinct_from_stream_parse_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            home.mkdir()
            result = probe._run_streaming_process(
                ["python3", "-c", "raise SystemExit(7)"],
                cwd=root,
                env={"PATH": "/usr/bin:/bin"},
                timeout_seconds=2,
                events_path=root / "events.jsonl",
                stderr_path=root / "stderr.log",
                secrets=(),
                credential_home=home,
                credential_paths=(),
            )

        self.assertEqual(result.status, "non-zero-exit")
        self.assertEqual(result.exit_code, 7)

    def test_auth_template_rejects_symlinks_and_user_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "template"
            template.mkdir()
            (template / "escape").symlink_to(root)
            with self.assertRaises(probe.ProbeError):
                probe._copy_auth_template(template, root / "home")

            (template / "escape").unlink()
            skill = template / ".cursor" / "skills" / "inherited" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("not allowed\n", encoding="utf-8")
            with self.assertRaises(probe.ProbeError):
                probe._copy_auth_template(template, root / "home")

    def test_plaintext_auth_material_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template = Path(temp_dir)
            marker = "fixture-redaction-marker-" + "x" * 16
            (template / "auth-data.txt").write_text(f"VALUE={marker}\n", encoding="utf-8")

            redactions = probe._credential_redactions(template)
            sanitized = probe._redact(f"value={marker}\n".encode(), redactions)

        self.assertNotIn(marker.encode(), sanitized)

    def test_permission_echo_uses_structured_tool_outcome(self) -> None:
        def event(result):
            return {
                "type": "tool_call",
                "subtype": "completed",
                "tool_call": {
                    "shellToolCall": {
                        "args": {"command": "echo permission-precedence-probe"},
                        "result": result,
                    }
                },
            }

        self.assertTrue(probe._permission_echo_denied([event({"success": False})]))
        self.assertFalse(probe._permission_echo_denied([event({"success": {"output": "probe"}})]))
        self.assertTrue(probe._permission_echo_denied([event({"error": "denied"})]))

    def test_behavior_artifact_requires_successful_probe_action_tool_call(self) -> None:
        successful = {
            "type": "tool_call",
            "subtype": "completed",
            "tool_call": {
                "shellToolCall": {
                    "args": {"command": "python3 probe_action.py"},
                    "result": {"success": {"output": ""}},
                }
            },
        }
        direct_artifact = {
            "type": "tool_call",
            "subtype": "completed",
            "tool_call": {
                "shellToolCall": {
                    "args": {"command": "echo '{}' > probe-observation.json"},
                    "result": {"success": {"output": ""}},
                }
            },
        }

        self.assertTrue(probe._behavior_action_completed([successful]))
        self.assertIsNone(probe._behavior_action_completed([direct_artifact]))

    def test_relative_event_path_is_resolved_before_containment_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "run" / "workspace"
            home = root / "run" / "home"
            workspace.mkdir(parents=True)
            home.mkdir()
            events = [
                {"tool_call": {"readToolCall": {"args": {"path": "../../../outside/file.txt"}}}}
            ]

            paths = probe._event_paths(events, default_cwd=workspace, home=home)

        self.assertEqual(paths, (str((root.parent / "outside" / "file.txt").resolve()),))

    def test_mcp_side_effect_is_not_attributed_to_agent_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            auth_template = output_root / "auth-template"
            auth_template.mkdir()
            (auth_template / "auth-data.txt").write_text("fixture\n", encoding="utf-8")

            def fake_run_text(_command, *, cwd, **_kwargs):
                (cwd / "mcp-side-effect.txt").write_text("mcp\n", encoding="utf-8")
                return "No MCP servers configured"

            def fake_stream(_command, *, cwd, events_path, **_kwargs):
                self.assertTrue((cwd / "mcp-side-effect.txt").is_file())
                events = [
                    {
                        "type": "system",
                        "subtype": "init",
                        "session_id": "mcp-snapshot-session",
                        "model": "gpt-5",
                        "cwd": str(cwd),
                    },
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": "done",
                        "session_id": "mcp-snapshot-session",
                    },
                ]
                events_path.write_text(
                    "\n".join(json.dumps(event) for event in events) + "\n",
                    encoding="utf-8",
                )
                return probe.ProcessResult("completed", 0, 0.1, True)

            with mock.patch.object(probe, "_run_text", side_effect=fake_run_text):
                with mock.patch.object(
                    probe,
                    "_run_streaming_process",
                    side_effect=fake_stream,
                ):
                    summary, _parsed = probe._run_live_case(
                        executable="/tmp/agent",
                        auth_template=auth_template,
                        output_root=output_root,
                        case_id="snapshot-boundary",
                        prompt="probe",
                        model="gpt-5",
                        mode="plan",
                        force=False,
                        behavior=False,
                        timeout_seconds=1,
                    )

        self.assertTrue(summary["mcp_workspace_mutated"])
        self.assertFalse(summary["workspace_mutated"])

    def test_behavior_artifact_without_probe_action_evidence_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            auth_template = output_root / "auth-template"
            auth_template.mkdir()

            def fake_stream(_command, *, cwd, events_path, **_kwargs):
                (cwd / "probe-observation.json").write_text(
                    json.dumps(
                        {
                            "workspace_write": True,
                            "outside_write": False,
                            "symlink_escape_write": False,
                            "cursor_api_key_visible": False,
                            "cursor_auth_token_visible": False,
                            "secret_canary_visible": False,
                            "credential_canary_visible": False,
                        }
                    ),
                    encoding="utf-8",
                )
                events = [
                    {
                        "type": "system",
                        "subtype": "init",
                        "session_id": "forged-artifact-session",
                        "model": "gpt-5",
                        "cwd": str(cwd),
                    },
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": "done",
                        "session_id": "forged-artifact-session",
                    },
                ]
                events_path.write_text(
                    "\n".join(json.dumps(event) for event in events) + "\n",
                    encoding="utf-8",
                )
                return probe.ProcessResult("completed", 0, 0.1, True)

            with mock.patch.object(
                probe,
                "_run_text",
                return_value="No MCP servers configured",
            ):
                with mock.patch.object(
                    probe,
                    "_run_streaming_process",
                    side_effect=fake_stream,
                ):
                    summary, _parsed = probe._run_live_case(
                        executable="/tmp/agent",
                        auth_template=auth_template,
                        output_root=output_root,
                        case_id="forged-artifact",
                        prompt="probe",
                        model="gpt-5",
                        mode="ask",
                        force=True,
                        behavior=True,
                        timeout_seconds=1,
                    )

        self.assertIsNone(summary["behavior_action_completed"])
        self.assertTrue(summary["behavior_script_unchanged"])
        self.assertIsNone(summary["behavior_observation"]["workspace_write"])

    def test_generated_behavior_action_is_valid_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = probe._prepare_workspace(Path(temp_dir), behavior=True)
            completed = subprocess.run(
                ["python3", "probe_action.py"],
                cwd=workspace,
                check=False,
            )

            observation = json.loads(
                (workspace / "probe-observation.json").read_text(encoding="utf-8")
            )

        self.assertEqual(completed.returncode, 0)
        self.assertTrue(observation["workspace_write"])


if __name__ == "__main__":
    unittest.main()
