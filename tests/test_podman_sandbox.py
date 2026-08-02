from __future__ import annotations

import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "scripts"))

from skill_eval.core import EvalError  # noqa: E402
from skill_eval.sandbox import PodmanSandboxRunner, SandboxPolicy  # noqa: E402

PODMAN_TEST_IMAGE = os.environ.get("SKILLS_NEXUS_PODMAN_TEST_IMAGE")


class PodmanSandboxContractTests(unittest.TestCase):
    def _runner(self) -> PodmanSandboxRunner:
        payload = {"host": {"security": {"rootless": True}}, "version": {"Version": "5.8.4"}}
        probe = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload).encode(), stderr=b""
        )
        with (
            mock.patch("skill_eval.sandbox.shutil.which", return_value="/usr/bin/podman"),
            mock.patch("skill_eval.sandbox.subprocess.run", return_value=probe),
        ):
            return PodmanSandboxRunner()

    def test_runtime_must_be_rootless(self) -> None:
        payload = {
            "host": {"security": {"rootless": False}},
            "version": {"Version": "5.8.4"},
        }
        probe = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload).encode(), stderr=b""
        )
        with (
            mock.patch("skill_eval.sandbox.shutil.which", return_value="/usr/bin/podman"),
            mock.patch("skill_eval.sandbox.subprocess.run", return_value=probe),
            self.assertRaisesRegex(EvalError, "requires a rootless runtime"),
        ):
            PodmanSandboxRunner()

    def test_command_enforces_disposable_boundary_and_contains_no_secret_values(self) -> None:
        runner = self._runner()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            command = runner._build_command(
                run_id="abc123",
                image="example@sha256:deadbeef",
                workspace=workspace,
                command=("agent", "--print"),
                policy=SandboxPolicy(),
                secret_names=("CURSOR_API_KEY",),
                cidfile=workspace / "container.cid",
            )

        rendered = "\n".join(command)
        self.assertIn("--env=CURSOR_API_KEY", command)
        self.assertFalse(
            [argument for argument in command if argument.startswith("--env=CURSOR_API_KEY=")],
            command,
        )
        for expected in (
            "--rm",
            "--pull=never",
            f"--cidfile={workspace / 'container.cid'}",
            "--read-only",
            "--read-only-tmpfs=false",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--userns=keep-id",
            "--pids-limit=64",
            "--memory=1073741824",
            "--memory-swap=1073741824",
            "--cpus=1.0",
            "--network=none",
            "--http-proxy=false",
            "--unsetenv-all",
            "--env=HOME=/sandbox-home",
            f"src={workspace},target=/workspace,rw",
            "relabel=private",
            "--workdir=/workspace",
        ):
            self.assertIn(expected, rendered)
        self.assertNotIn("--security-opt=label=disable", command)

    def test_private_network_never_uses_host_networking(self) -> None:
        runner = self._runner()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            command = runner._build_command(
                run_id="abc123",
                image="image-id",
                workspace=workspace,
                command=("true",),
                policy=SandboxPolicy(network="private"),
                secret_names=(),
                cidfile=workspace / "container.cid",
            )

        self.assertIn("--network=slirp4netns:allow_host_loopback=false", command)
        self.assertNotIn("--network=host", command)

    def test_invalid_inputs_fail_before_execution(self) -> None:
        runner = self._runner()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            with self.assertRaisesRegex(EvalError, "command must not be empty"):
                runner.run(image="image-id", workspace=workspace, command=())
            with self.assertRaisesRegex(EvalError, "invalid sandbox secret"):
                runner.run(
                    image="image-id",
                    workspace=workspace,
                    command=("true",),
                    secrets={"BAD-NAME": "value"},
                )
            with self.assertRaisesRegex(EvalError, "reserved environment name"):
                runner.run(
                    image="image-id",
                    workspace=workspace,
                    command=("true",),
                    secrets={"HOME": "host-home"},
                )
        for value in (float("nan"), float("inf"), float("-inf")):
            with (
                self.subTest(non_finite=value),
                self.assertRaisesRegex(EvalError, "must be positive"),
            ):
                SandboxPolicy(timeout_seconds=value)

    def test_cleanup_timeout_is_reported_without_raising(self) -> None:
        runner = self._runner()
        with mock.patch(
            "skill_eval.sandbox.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["podman", "rm"], 15),
        ):
            completed, error = runner._force_remove("container-name")

        self.assertFalse(completed)
        self.assertIn("timed out", error)

    def test_process_start_failure_returns_normalized_failed_result(self) -> None:
        runner = self._runner()
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch("skill_eval.sandbox.subprocess.Popen", side_effect=OSError("unavailable")),
            mock.patch.object(runner, "_force_remove", return_value=(True, "")),
        ):
            result = runner.run(
                image="image-id",
                workspace=Path(temporary),
                command=("true",),
            )

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.exit_code)
        self.assertIn("could not start", result.stderr)
        self.assertTrue(result.cleanup_completed)

    def test_cancellation_set_during_final_wait_wins_over_process_exit(self) -> None:
        runner = self._runner()
        cancel = threading.Event()

        class ExitingProcess:
            pid = 999_999
            returncode = 0
            stdout = io.BytesIO()
            stderr = io.BytesIO()

            def wait(self, timeout: float | None = None) -> int:
                cancel.set()
                return 0

            def poll(self) -> int:
                return 0

        process = ExitingProcess()
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch("skill_eval.sandbox.subprocess.Popen", return_value=process),
            mock.patch.object(runner, "_force_remove", return_value=(True, "")) as remove,
        ):
            result = runner.run(
                image="image-id",
                workspace=Path(temporary),
                command=("true",),
                cancel_event=cancel,
            )

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(remove.call_count, 2)


@unittest.skipUnless(
    PODMAN_TEST_IMAGE,
    "set SKILLS_NEXUS_PODMAN_TEST_IMAGE to a preloaded local image for adversarial tests",
)
class PodmanSandboxAdversarialTests(unittest.TestCase):
    runner: PodmanSandboxRunner
    image: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = PodmanSandboxRunner()
        cls.image = PODMAN_TEST_IMAGE or ""

    def _assert_container_removed(self, run_id: str) -> None:
        probe = subprocess.run(
            [
                self.runner.podman_binary,
                "ps",
                "--all",
                "--quiet",
                "--filter",
                f"label={self.runner.label_key}={run_id}",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(probe.stdout.strip(), "")

    def test_blocks_host_reads_writes_symlink_escape_and_personal_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            outside = root / "outside"
            workspace.mkdir()
            outside.mkdir()
            personal_home = root / "personal-home"
            personal_sentinel = personal_home / ".cursor" / "rules" / "personal.mdc"
            personal_sentinel.parent.mkdir(parents=True)
            personal_sentinel.write_text("personal context must stay on host\n", encoding="utf-8")
            host_canary = outside / "host-canary"
            host_canary.write_text("host-private\n", encoding="utf-8")
            host_target = outside / "host-target"
            host_target.write_text("unchanged\n", encoding="utf-8")
            (workspace / "escape").symlink_to(host_target)
            hostile_config = root / "host-config"
            hostile_containers = hostile_config / "containers"
            hostile_containers.mkdir(parents=True)
            (hostile_containers / "mounts.conf").write_text(
                (f"{outside}:/inherited-host-mount\n{personal_home}:/inherited-personal-home\n"),
                encoding="utf-8",
            )
            script = "\n".join(
                (
                    "set -eu",
                    f"test ! -e {shlex.quote(str(host_canary))}",
                    f"! cat {shlex.quote(str(host_canary))}",
                    f"! printf compromised > {shlex.quote(str(host_target))}",
                    "! printf escaped > /workspace/escape",
                    f"test ! -e {shlex.quote(str(personal_sentinel))}",
                    "test ! -e /sandbox-home/.cursor",
                    "test ! -e /sandbox-home/.ssh",
                    "test ! -e /inherited-host-mount",
                    "test ! -e /inherited-personal-home",
                    "test ! -e /run/secrets/etc-pki-entitlement",
                    'test -z "${HOST_ENV_CANARY+x}"',
                    'test -z "${HTTP_PROXY+x}"',
                    'test "$(ls /sys/class/net)" = lo',
                    "printf workspace-ok > /workspace/result",
                )
            )
            with mock.patch.dict(
                os.environ,
                {
                    "HOST_ENV_CANARY": "must-not-cross",
                    "HTTP_PROXY": "http://host-proxy.invalid:9999",
                    "XDG_CONFIG_HOME": str(hostile_config),
                },
            ):
                result = self.runner.run(
                    image=self.image,
                    workspace=workspace,
                    command=("/bin/sh", "-c", script),
                    policy=SandboxPolicy(timeout_seconds=10),
                )

            self.assertEqual(result.status, "completed", result.stderr)
            self.assertTrue(result.cleanup_completed)
            self.assertEqual(host_target.read_text(encoding="utf-8"), "unchanged\n")
            self.assertEqual((workspace / "result").read_text(encoding="utf-8"), "workspace-ok")
            self._assert_container_removed(result.run_id)

    def test_redacts_secret_and_removes_failure_home_and_container(self) -> None:
        secret = "cursor-secret-runtime-only-7f3c"
        temporary_before = set(Path(tempfile.gettempdir()).glob("skill-eval-podman-*"))
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            result = self.runner.run(
                image=self.image,
                workspace=workspace,
                command=(
                    "/bin/sh",
                    "-c",
                    'printf "%s" "$CURSOR_API_KEY"; printf state > "$HOME/credential-state"; exit 7',
                ),
                policy=SandboxPolicy(timeout_seconds=10),
                secrets={"CURSOR_API_KEY": secret},
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.exit_code, 7)
        self.assertNotIn(secret, result.stdout)
        self.assertEqual(result.stdout, "[REDACTED]")
        self.assertEqual(
            set(Path(tempfile.gettempdir()).glob("skill-eval-podman-*")), temporary_before
        )
        self._assert_container_removed(result.run_id)

    def test_secret_crossing_output_limit_is_redacted_before_truncation(self) -> None:
        secret = "cursor-secret-crossing-output-boundary"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.runner.run(
                image=self.image,
                workspace=Path(temporary),
                command=("/bin/sh", "-c", 'printf "123456789%s" "$CURSOR_API_KEY"'),
                policy=SandboxPolicy(timeout_seconds=10, max_output_bytes=10),
                secrets={"CURSOR_API_KEY": secret},
            )

        self.assertEqual(result.status, "completed", result.stderr)
        self.assertEqual(result.stdout, "123456789[")
        self.assertNotIn(secret[:2], result.stdout)
        self.assertTrue(result.output_truncated)
        self._assert_container_removed(result.run_id)

    def test_repeated_secret_beyond_capture_limit_discards_stream(self) -> None:
        secret_value = "repeated-runtime-secret-value"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.runner.run(
                image=self.image,
                workspace=Path(temporary),
                command=(
                    "/bin/sh",
                    "-c",
                    'printf "%s%s%s%s%s%s" "$API_KEY" "$API_KEY" "$API_KEY" '
                    '"$API_KEY" "$API_KEY" "$API_KEY"',
                ),
                policy=SandboxPolicy(timeout_seconds=10, max_output_bytes=32),
                secrets={"API_KEY": secret_value},
            )

        self.assertEqual(result.status, "completed", result.stderr)
        self.assertTrue(result.stdout.startswith("[REDACTED:"))
        self.assertNotIn(secret_value[:5], result.stdout)
        self.assertTrue(result.output_truncated)
        self._assert_container_removed(result.run_id)

    def test_multiple_secrets_beyond_capture_limit_discard_stream(self) -> None:
        first_value = "first-runtime-secret-value-12345"
        second_value = "second-runtime-secret-value-67890"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.runner.run(
                image=self.image,
                workspace=Path(temporary),
                command=("/bin/sh", "-c", 'printf "%s%s" "$FIRST_KEY" "$SECOND_KEY"'),
                policy=SandboxPolicy(timeout_seconds=10, max_output_bytes=20),
                secrets={"FIRST_KEY": first_value, "SECOND_KEY": second_value},
            )

        self.assertEqual(result.status, "completed", result.stderr)
        self.assertTrue(result.stdout.startswith("[REDACTED:"))
        self.assertNotIn(first_value[:5], result.stdout)
        self.assertNotIn(second_value[:5], result.stdout)
        self.assertTrue(result.output_truncated)
        self._assert_container_removed(result.run_id)

    def test_timeout_forces_container_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.runner.run(
                image=self.image,
                workspace=Path(temporary),
                command=("/bin/sh", "-c", "sleep 30"),
                policy=SandboxPolicy(timeout_seconds=0.2),
            )

        self.assertEqual(result.status, "timed-out")
        self.assertTrue(result.cleanup_completed)
        self._assert_container_removed(result.run_id)

    def test_cancellation_forces_container_cleanup(self) -> None:
        cancel = threading.Event()
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                result = self.runner.run(
                    image=self.image,
                    workspace=Path(temporary),
                    command=("/bin/sh", "-c", "sleep 30"),
                    policy=SandboxPolicy(timeout_seconds=10),
                    cancel_event=cancel,
                )
        finally:
            timer.cancel()

        self.assertEqual(result.status, "cancelled")
        self.assertTrue(result.cleanup_completed)
        self._assert_container_removed(result.run_id)


if __name__ == "__main__":
    unittest.main()
