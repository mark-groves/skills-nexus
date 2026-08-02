"""Rootless Podman execution boundary for evaluation harness adapters."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from .core import EvalError

SandboxNetwork = Literal["none", "private"]
SandboxStatus = Literal["completed", "failed", "timed-out", "cancelled", "cleanup-failed"]

_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONTAINER_HOME = "/sandbox-home"
_CONTAINER_WORKSPACE = "/workspace"
_REDACTION = "[REDACTED]"
_TRUNCATED_SECRET_OUTPUT = "[REDACTED: SECRET-BEARING OUTPUT TRUNCATED]"
_SAFE_HOST_ENVIRONMENT = (
    "DBUS_SESSION_BUS_ADDRESS",
    "HOME",
    "PATH",
    "TMPDIR",
    "XDG_RUNTIME_DIR",
)
_CONTAINER_ENVIRONMENT_NAMES = frozenset(
    {
        *_SAFE_HOST_ENVIRONMENT,
        "LANG",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
)


@dataclass(frozen=True)
class SandboxPolicy:
    """Resource and connectivity limits applied to every container run."""

    timeout_seconds: float = 300.0
    pids_limit: int = 64
    memory_bytes: int = 1_073_741_824
    cpus: float = 1.0
    network: SandboxNetwork = "none"
    temporary_storage_bytes: int = 67_108_864
    max_output_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        positive_values = (
            (self.timeout_seconds, "timeout_seconds"),
            (self.pids_limit, "pids_limit"),
            (self.memory_bytes, "memory_bytes"),
            (self.cpus, "cpus"),
            (self.temporary_storage_bytes, "temporary_storage_bytes"),
            (self.max_output_bytes, "max_output_bytes"),
        )
        for value, name in positive_values:
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise EvalError(f"sandbox {name} must be positive")
        if self.network not in {"none", "private"}:
            raise EvalError("sandbox network must be 'none' or 'private'")


@dataclass(frozen=True)
class SandboxResult:
    """Bounded, redacted result returned to a harness adapter."""

    run_id: str
    status: SandboxStatus
    exit_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    output_truncated: bool
    cleanup_completed: bool

    def as_dict(self) -> dict[str, str | int | float | bool | None]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 6),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "output_truncated": self.output_truncated,
            "cleanup_completed": self.cleanup_completed,
        }


class _BoundedCapture:
    def __init__(self, internal_limit: int) -> None:
        self.internal_limit = internal_limit
        self.buffer = bytearray()
        self.truncated = False

    def drain(self, stream: BinaryIO) -> None:
        try:
            while chunk := stream.read(65_536):
                remaining = self.internal_limit - len(self.buffer)
                if remaining > 0:
                    self.buffer.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        finally:
            stream.close()

    def text(self) -> str:
        return self.buffer.decode("utf-8", errors="replace")


class PodmanSandboxRunner:
    """Execute one command in a disposable, rootless Podman container."""

    label_key = "io.skills-nexus.sandbox-run"

    def __init__(self, *, podman_binary: str = "podman") -> None:
        resolved = shutil.which(podman_binary)
        if resolved is None:
            raise EvalError(f"Podman executable not found: {podman_binary}")
        self.podman_binary = resolved
        self.version = self._verify_rootless_runtime()

    def _host_environment(
        self,
        secrets: Mapping[str, str] | None = None,
        *,
        config_home: Path | None = None,
    ) -> dict[str, str]:
        environment = {
            name: os.environ[name] for name in _SAFE_HOST_ENVIRONMENT if name in os.environ
        }
        if secrets:
            environment.update(secrets)
        if config_home is not None:
            environment["XDG_CONFIG_HOME"] = str(config_home)
        return environment

    def _verify_rootless_runtime(self) -> str:
        try:
            probe = subprocess.run(
                [self.podman_binary, "info", "--format", "json"],
                capture_output=True,
                check=False,
                env=self._host_environment(),
                timeout=15,
            )
        except subprocess.TimeoutExpired as exc:
            raise EvalError("Podman runtime preflight timed out after 15 seconds") from exc
        except OSError as exc:
            raise EvalError(f"Podman runtime preflight could not start: {exc}") from exc
        if probe.returncode != 0:
            detail = probe.stderr.decode("utf-8", errors="replace").strip()
            raise EvalError(f"Podman runtime preflight failed: {detail or 'unknown error'}")
        try:
            payload = json.loads(probe.stdout)
            rootless = payload["host"]["security"]["rootless"]
            version = payload["version"]["Version"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EvalError("Podman runtime preflight returned malformed metadata") from exc
        if rootless is not True:
            raise EvalError("Podman sandbox runner requires a rootless runtime")
        if not isinstance(version, str) or not version.strip():
            raise EvalError("Podman runtime did not report an exact version")
        return f"podman {version.strip()}"

    @staticmethod
    def _validate_command(command: Sequence[str]) -> tuple[str, ...]:
        if not command:
            raise EvalError("sandbox command must not be empty")
        normalized = tuple(command)
        if any(not isinstance(item, str) or not item or "\0" in item for item in normalized):
            raise EvalError("sandbox command arguments must be non-empty strings without NUL")
        return normalized

    @staticmethod
    def _validate_secrets(secrets: Mapping[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for name, value in secrets.items():
            if not isinstance(name, str) or not _ENVIRONMENT_NAME.fullmatch(name):
                raise EvalError(f"invalid sandbox secret environment name: {name!r}")
            if not isinstance(value, str) or not value or "\0" in value:
                raise EvalError(f"sandbox secret {name!r} must be a non-empty string without NUL")
            if name in _CONTAINER_ENVIRONMENT_NAMES:
                raise EvalError(
                    f"sandbox secret {name!r} conflicts with a reserved environment name"
                )
            normalized[name] = value
        return normalized

    @staticmethod
    def _workspace(path: Path) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise EvalError(f"sandbox workspace could not be resolved: {exc}") from exc
        if not resolved.is_dir():
            raise EvalError(f"sandbox workspace is not a directory: {resolved}")
        return resolved

    def _build_command(
        self,
        *,
        run_id: str,
        image: str,
        workspace: Path,
        command: tuple[str, ...],
        policy: SandboxPolicy,
        secret_names: tuple[str, ...],
        cidfile: Path,
    ) -> list[str]:
        if not image.strip() or "\0" in image or image.startswith("-"):
            raise EvalError("sandbox image must be a non-option reference without NUL")
        name = f"skills-nexus-eval-{run_id}"
        memory = str(policy.memory_bytes)
        temporary_storage = str(policy.temporary_storage_bytes)
        network = "none" if policy.network == "none" else "slirp4netns:allow_host_loopback=false"
        result = [
            self.podman_binary,
            "run",
            "--rm",
            "--pull=never",
            f"--name={name}",
            f"--cidfile={cidfile}",
            f"--label={self.label_key}={run_id}",
            "--read-only",
            "--read-only-tmpfs=false",
            "--image-volume=ignore",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--userns=keep-id",
            f"--user={os.getuid()}:{os.getgid()}",
            "--ipc=private",
            "--pid=private",
            "--uts=private",
            f"--pids-limit={policy.pids_limit}",
            f"--memory={memory}",
            f"--memory-swap={memory}",
            f"--cpus={policy.cpus}",
            f"--network={network}",
            "--stop-timeout=1",
            "--http-proxy=false",
            "--unsetenv-all",
            f"--env=HOME={_CONTAINER_HOME}",
            f"--env=XDG_CONFIG_HOME={_CONTAINER_HOME}/.config",
            f"--env=XDG_DATA_HOME={_CONTAINER_HOME}/.local/share",
            f"--env=XDG_CACHE_HOME={_CONTAINER_HOME}/.cache",
            f"--env=XDG_STATE_HOME={_CONTAINER_HOME}/.local/state",
            "--env=TMPDIR=/tmp",
            "--env=LANG=C.UTF-8",
            "--env=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            (
                f"--tmpfs={_CONTAINER_HOME}:rw,nodev,nosuid,noexec,"
                f"size={temporary_storage},mode=1777"
            ),
            f"--tmpfs=/tmp:rw,nodev,nosuid,noexec,size={temporary_storage},mode=1777",
            f"--tmpfs=/run:rw,nodev,nosuid,noexec,size={temporary_storage},mode=755",
            (f"--mount=type=bind,src={workspace},target={_CONTAINER_WORKSPACE},rw,relabel=private"),
            f"--workdir={_CONTAINER_WORKSPACE}",
        ]
        result.extend(f"--env={name}" for name in secret_names)
        result.append(image)
        result.extend(command)
        return result

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=1)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

    def _force_remove(self, name: str, *, config_home: Path | None = None) -> tuple[bool, str]:
        try:
            cleanup = subprocess.run(
                [self.podman_binary, "rm", "--force", "--ignore", name],
                capture_output=True,
                check=False,
                env=self._host_environment(config_home=config_home),
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return False, "Podman container removal timed out after 15 seconds"
        except OSError as exc:
            return False, f"Podman container removal could not start: {exc}"
        error = cleanup.stderr.decode("utf-8", errors="replace").strip()
        return cleanup.returncode == 0, error

    @staticmethod
    def _cleanup_target(name: str, cidfile: Path) -> str:
        try:
            container_id = cidfile.read_text(encoding="utf-8").strip()
        except OSError:
            return name
        return container_id if re.fullmatch(r"[0-9a-f]{64}", container_id) else name

    @staticmethod
    def _redact(text: str, secrets: Mapping[str, str]) -> str:
        for value in sorted(set(secrets.values()), key=len, reverse=True):
            text = text.replace(value, _REDACTION)
        return text

    @classmethod
    def _redacted_capture(
        cls,
        capture: _BoundedCapture,
        secrets: Mapping[str, str],
        exposed_limit: int,
        *,
        incomplete: bool = False,
    ) -> tuple[str, bool]:
        if incomplete:
            bounded, _ = cls._bounded_text("[INCOMPLETE OUTPUT CAPTURE]", exposed_limit)
            return bounded, True
        if capture.truncated and secrets:
            bounded, _ = cls._bounded_text(_TRUNCATED_SECRET_OUTPUT, exposed_limit)
            return bounded, True
        redacted = cls._redact(capture.text(), secrets)
        encoded = redacted.encode("utf-8")
        truncated = capture.truncated or len(encoded) > exposed_limit
        return encoded[:exposed_limit].decode("utf-8", errors="replace"), truncated

    @staticmethod
    def _bounded_text(text: str, exposed_limit: int) -> tuple[str, bool]:
        encoded = text.encode("utf-8")
        return (
            encoded[:exposed_limit].decode("utf-8", errors="replace"),
            len(encoded) > exposed_limit,
        )

    def run(
        self,
        *,
        image: str,
        workspace: Path,
        command: Sequence[str],
        policy: SandboxPolicy | None = None,
        secrets: Mapping[str, str] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> SandboxResult:
        """Run a command and force cleanup after success, failure, timeout, or cancellation."""

        selected_policy = policy or SandboxPolicy()
        resolved_workspace = self._workspace(workspace)
        normalized_command = self._validate_command(command)
        normalized_secrets = self._validate_secrets(secrets or {})
        run_id = uuid.uuid4().hex
        name = f"skills-nexus-eval-{run_id}"
        started = time.monotonic()
        status: SandboxStatus = "failed"
        exit_code: int | None = None
        cleanup_completed = False
        cleanup_error = ""
        process: subprocess.Popen[bytes] | None = None
        secret_margin = max(
            (len(value.encode("utf-8")) - 1 for value in normalized_secrets.values()),
            default=0,
        )
        internal_output_limit = selected_policy.max_output_bytes + secret_margin
        stdout_capture = _BoundedCapture(internal_output_limit)
        stderr_capture = _BoundedCapture(internal_output_limit)
        capture_threads: list[threading.Thread] = []
        startup_error = ""
        capture_incomplete = False

        with tempfile.TemporaryDirectory(prefix="skill-eval-podman-") as temporary:
            temporary_root = Path(temporary)
            cidfile = temporary_root / "container.cid"
            config_home = temporary_root / "client-config"
            containers_config = config_home / "containers"
            containers_config.mkdir(parents=True, mode=0o700)
            mounts_config = containers_config / "mounts.conf"
            mounts_config.write_text("", encoding="utf-8")
            mounts_config.chmod(0o600)
            podman_command = self._build_command(
                run_id=run_id,
                image=image,
                workspace=resolved_workspace,
                command=normalized_command,
                policy=selected_policy,
                secret_names=tuple(normalized_secrets),
                cidfile=cidfile,
            )
            try:
                try:
                    process = subprocess.Popen(
                        podman_command,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=self._host_environment(
                            normalized_secrets,
                            config_home=config_home,
                        ),
                        start_new_session=True,
                    )
                    if process.stdout is None or process.stderr is None:
                        raise EvalError("Podman process pipes were not available")
                    capture_threads = [
                        threading.Thread(
                            target=stdout_capture.drain, args=(process.stdout,), daemon=True
                        ),
                        threading.Thread(
                            target=stderr_capture.drain, args=(process.stderr,), daemon=True
                        ),
                    ]
                    for thread in capture_threads:
                        thread.start()

                    deadline = started + selected_policy.timeout_seconds
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            status = "cancelled"
                            break
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            status = "timed-out"
                            break
                        try:
                            exit_code = process.wait(timeout=min(0.1, remaining))
                        except subprocess.TimeoutExpired:
                            continue
                        if cancel_event is not None and cancel_event.is_set():
                            status = "cancelled"
                        else:
                            status = "completed" if exit_code == 0 else "failed"
                        break
                except (OSError, subprocess.SubprocessError, EvalError) as exc:
                    startup_error = f"Podman process could not start: {exc}"
                    status = "failed"
            finally:
                try:
                    cleanup_completed, cleanup_error = self._force_remove(
                        name,
                        config_home=config_home,
                    )
                finally:
                    if process is not None:
                        self._terminate_process(process)
                        if exit_code is None and process.returncode is not None:
                            exit_code = process.returncode
                    for thread in capture_threads:
                        thread.join(timeout=2)
                        capture_incomplete = capture_incomplete or thread.is_alive()
                if process is not None:
                    cleanup_target = self._cleanup_target(name, cidfile)
                    retry_completed, retry_error = self._force_remove(
                        cleanup_target,
                        config_home=config_home,
                    )
                    cleanup_completed = retry_completed
                    cleanup_error = "\n".join(
                        error for error in (cleanup_error, retry_error) if error
                    )

        if capture_incomplete and status == "completed":
            status = "failed"
            startup_error = "Podman output capture did not finish after process termination"

        stdout, stdout_truncated = self._redacted_capture(
            stdout_capture,
            normalized_secrets,
            selected_policy.max_output_bytes,
            incomplete=capture_incomplete,
        )
        stderr, stderr_truncated = self._redacted_capture(
            stderr_capture,
            normalized_secrets,
            selected_policy.max_output_bytes,
            incomplete=capture_incomplete,
        )
        if startup_error:
            redacted_startup_error = self._redact(startup_error, normalized_secrets)
            stderr = f"{stderr.rstrip()}\n{redacted_startup_error}".lstrip()
        cleanup_error = self._redact(cleanup_error, normalized_secrets)
        if not cleanup_completed:
            status = "cleanup-failed"
            if cleanup_error:
                stderr = f"{stderr.rstrip()}\ncontainer cleanup failed: {cleanup_error}".lstrip()
        stderr, diagnostic_truncated = self._bounded_text(
            stderr,
            selected_policy.max_output_bytes,
        )
        return SandboxResult(
            run_id=run_id,
            status=status,
            exit_code=exit_code,
            duration_seconds=time.monotonic() - started,
            stdout=stdout,
            stderr=stderr,
            output_truncated=stdout_truncated or stderr_truncated or diagnostic_truncated,
            cleanup_completed=cleanup_completed,
        )


__all__ = ["PodmanSandboxRunner", "SandboxPolicy", "SandboxResult"]
