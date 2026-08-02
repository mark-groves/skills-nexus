# Rootless evaluation sandbox runner

The evaluator provides an adapter-neutral `PodmanSandboxRunner` for harnesses
that require an externally enforced execution boundary. It is infrastructure
beneath the task/judge adapter registry, not a Cursor adapter, and the existing
Codex adapter does not use it or change behavior.

Each invocation requires an already-present container image and a single
evaluation workspace. The runner refuses non-rootless Podman, disables implicit
image pulls, and starts a disposable container with:

- only the resolved workspace bind-mounted at `/workspace`;
- a private SELinux relabel on that disposable workspace mount, retaining host
  MAC enforcement without exposing any other host directory;
- a read-only root filesystem plus bounded tmpfs mounts for an empty home,
  `/tmp`, and `/run`;
- no inherited host environment, home, SSH files, Cursor profile, rules, skills,
  MCP configuration, project directories, or history;
- an isolated Podman client configuration with an empty `mounts.conf`, plus host
  proxy forwarding disabled, so user-level default mounts and proxy variables
  cannot silently widen the boundary;
- dropped capabilities, `no-new-privileges`, a private user/PID/IPC/UTS
  namespace, and explicit CPU, process, memory, swap, time, and output limits;
- either no network (the default) or rootless `slirp4netns` with host loopback
  disabled; and
- a unique name and label that are force-removed in a `finally` path after
  success, failure, timeout, explicit cancellation, or an exception.

Secrets are accepted only as an in-memory mapping. Podman receives `--env NAME`
rather than `--env NAME=value`, so secret values are absent from the command
line. The runner exposes only those named variables to the container, removes
the disposable container and its tmpfs home, and redacts direct occurrences of
every supplied value in bounded stdout, stderr, and cleanup diagnostics. If a
secret-bearing stream crosses the internal capture bound, the runner discards
that entire captured stream instead of risking disclosure of a partial value.
Harnesses must treat `timed-out`, `cancelled`, `cleanup-failed`, non-zero exit,
or truncated output as non-success evidence.

Typical adapter use:

```python
from pathlib import Path

from skill_eval.sandbox import PodmanSandboxRunner, SandboxPolicy

result = PodmanSandboxRunner().run(
    image="localhost/eval-harness@sha256:<digest>",
    workspace=Path("/path/to/disposable/evaluation-workspace"),
    command=("harness-cli", "--machine-readable"),
    policy=SandboxPolicy(network="private", timeout_seconds=120),
    secrets={"HARNESS_API_KEY": runtime_api_key},
)
```

The image must be provisioned and reviewed separately. `--pull=never` prevents a
run from silently changing its executable substrate or contacting a registry.
User `containers.conf` and `storage.conf` are deliberately not inherited because
they can widen execution policy; images must therefore be present in the default
rootless store visible under the isolated client configuration. A custom-only
graph root fails closed as an unavailable image.
The `private` network mode permits outbound network access and is not a domain
allowlist; adapters should retain the default `none` unless an authenticated API
turn requires egress. No mode exposes the host network namespace or host
loopback.

## Boundary proof

Fast contract tests always verify rootless refusal, the exact resource/isolation
flags, runtime-only secret argument construction, and network selection. Live
adversarial tests are opt-in because CI hosts do not necessarily provide
rootless Podman. From the repository root, point them at a preloaded local image
containing `/bin/sh` plus `cat`, `ls`, `printf`, `sleep`, and `test` (BusyBox
applets are sufficient):

```bash
SKILLS_NEXUS_PODMAN_TEST_IMAGE=<local-image-id-or-digest> \
  python3 -m unittest tests.test_podman_sandbox
```

Those live tests execute inside the container and independently prove that host
canaries cannot be read or overwritten, an absolute symlink cannot escape the
workspace mount, a hostile shell write cannot affect the host, personal Cursor
context and an inherited environment canary are absent, networking is disabled,
workspace writes still work, returned secrets are redacted, and container/home
state is removed after success, failure, timeout, and cancellation.
