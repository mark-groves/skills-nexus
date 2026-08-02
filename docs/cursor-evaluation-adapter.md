# Cursor evaluation harness spike

Status: **probe complete; production Cursor adapter blocked**

Decision date: 2026-08-01

Issue: [#46](https://github.com/mark-groves/skills-nexus/issues/46)

## Decision

Use the Cursor Agent CLI as the **non-production probe substrate**. It fits the
repository's Python subprocess architecture and exposes an exact CLI version,
explicit model selection, a new session by default, workspace selection,
read-only modes, sandbox selection, and newline-delimited JSON.

Do not implement or enable a production Cursor task or judge adapter from this
spike. The current documented stream has no explicit skill-activation event, so
an exact completed read of the installed `SKILL.md` can prove `true`, but the
absence of that read cannot prove `false`. It must remain `unknown`. The live
credential, permission, workspace-containment, fresh-session, and model-match
matrix also remains unverified in this environment because the installed CLI is
not authenticated. Both facts are blocking evidence, not support to be inferred
or documented away.

A thin SDK bridge is not selected. No current public SDK contract was found that
provides stronger activation or credential-isolation evidence, while the CLI is
already sufficient to probe the subprocess and event boundaries. Issue #50 must
remain blocked until a dedicated browser-authenticated live probe passes every
hard gate or a later supported interface supplies the missing evidence.

## Verified interface

The local checks on 2026-08-01 found:

- Cursor desktop launcher: `3.14.7`, build
  `a758f2241ca99fecf380180b6cbdbbce0f1f42c0`, x64.
- Cursor Agent CLI: `2026.07.23-e383d2b`.
- `agent --help` exposes `--print`, `--model`, `--output-format stream-json`,
  `--mode`, `--sandbox`, `--trust`, `--workspace`, `--resume`, and `--force`.
- A fresh temporary `HOME` reports `isAuthenticated: false`; no API key or auth
  token was inherited for preflight.
- The installed CLI was not logged in, so no live model turn was attempted and
  no real credential was read, copied, printed, or placed in a checked-in file.

The current official documentation describes:

- [headless print mode and its write behavior](https://cursor.com/docs/cli/headless);
- the [NDJSON event and terminal-result contract](https://cursor.com/docs/cli/reference/output-format),
  including early termination on failure and forward-compatible field additions;
- [CLI authentication](https://cursor.com/docs/cli/reference/authentication),
  including browser login and `CURSOR_API_KEY` automation;
- [rules, MCP discovery, and session resume behavior](https://cursor.com/docs/cli/using);
- [permission configuration](https://cursor.com/docs/cli/github-actions); and
- [Agent Skills](https://cursor.com/docs/skills), including Cursor and shared
  project/user skill roots.

Documentation and `--help` are discovery evidence only. They do not prove that
the production-critical behavior works hermetically on this host.

## Activation evidence model

The normalized activation value is deliberately three-state:

- `true` — a completed read event names the exact clean `SKILL.md` installed for
  this invocation, or a future documented Cursor event explicitly reports the
  same activation;
- `false` — reserved for a future documented event that explicitly reports
  non-activation for that exact installed skill; and
- `unknown` — every other case, including a complete successful stream with no
  observed `SKILL.md` read.

The current parser can therefore produce `true` or `unknown`, but not `false`.
Model claims, response markers, and the absence of a tool event are not negative
activation evidence.

## Capability matrix

Capability results are `pass`, `fail`, or `unknown`. `pass` means the checked-in
probe or a local command produced direct evidence. `fail` means direct evidence
contradicts the property. `unknown` means the evidence is unavailable. The
production decision is separate: any `fail` or `unknown` hard gate blocks
eligibility.

| Capability | Result | Evidence and production effect |
| --- | --- | --- |
| CLI discovery and exact version | pass | Preflight resolves `agent` and captures `2026.07.23-e383d2b`. Each live run would capture again. |
| Explicit requested model | pass | The current CLI exposes `--model`; the probe always requires it. Mutable defaults are rejected by construction. |
| Requested-versus-reported model | unknown | The parser captures `system/init.model` and makes an exact mismatch visible. No authenticated live run proved that the reported display value is a stable identifier equal to the requested identifier, so production eligibility is blocked. |
| Fresh home | pass for construction | Preflight uses a new empty `HOME` and isolated XDG roots. Live mode copies only a dedicated browser-login template, adds one clean probe skill, and purges copied credential files at `system/init`. |
| Fresh session per invocation | unknown | Live mode omits `--resume`/`--continue` and requires four distinct session IDs, but no authenticated turns were available to prove uniqueness. |
| Selected Cursor skill root | pass for construction | The probe installs one clean copy at `~/.cursor/skills/cursor-evaluation-probe/SKILL.md` inside each fresh home. Discovery by the live agent is unknown. |
| Positive trigger | unknown | Live mode contains an exact positive case. It was not run. |
| Near-miss trigger | unknown | Live mode contains a related negative case. It was not run. |
| Activation `true` | pass for parser | Only an exact completed `readToolCall` for the installed `SKILL.md` produces `true`. |
| Activation `false` | fail | The documented stream has no explicit negative activation event. No observed read produces `unknown`, never `false`. This alone blocks a production CLI adapter. |
| Trigger workspace read-only | unknown | Live mode combines `plan`, `--sandbox enabled`, and before/after snapshots. It was not run. |
| Behavior workspace write | unknown | Live mode requires a write inside the evaluation workspace. It was not run. |
| Permission precedence | unknown | Live mode combines an allow rule, explicit deny, and `--force`, then requires the deny to win. It was not run. |
| Outside-workspace write | unknown | A bounded sibling directory is the escape target; any created file fails the gate. It was not run. |
| Symlink escape | unknown | A workspace symlink targets the bounded sibling directory; any created file fails the gate. It was not run. |
| User rules, skills, MCP, prior sessions | unknown | Fresh homes reject copied skills, rules, MCP, projects, and symlinks. Fresh workspaces contain no `.cursor/rules`, `.cursor/mcp.json`, root `mcp.json`, `AGENTS.md`, or `CLAUDE.md`; live mode also requires `agent mcp list` to report no configured servers and rejects event paths outside the run roots. Absence was not proved by authenticated turns, so production eligibility is blocked. |
| API key or auth token in agent shell | pass by construction | Live mode refuses inherited `CURSOR_API_KEY` and `CURSOR_AUTH_TOKEN`; it never accepts a secret on the command line. |
| Non-secret environment canary in agent shell | unknown | Live mode tests only a non-secret canary and requires it to be absent. It was not run. |
| Browser credential-file containment | unknown | Dedicated credentials are redacted from captured lines and deleted at `system/init`; a user/tool event before deletion terminates the process. The live boundary was not run. |
| Timeout and cancellation | pass | The bounded runner terminates the whole process group; automated tests exercise timeout, with cancellation following the same termination path. |
| Non-zero exit | pass | Automated tests keep it distinct from parse failure. A zero exit is still insufficient without a valid terminal event. |
| Partial stream | pass | Sanitized fixture without a terminal `result` fails closed. |
| Malformed event | pass | Sanitized malformed NDJSON fails closed with its line number. |
| Unknown future event/field | pass | Unknown event types and fields are recorded and tolerated without supplying evidence. |
| Existing JSON judgment contract | pass for parser; live unknown | A sanitized valid fixture passes the current two-candidate contract; omissions and extra fields fail. Cursor's live reliability is unverified. |
| Token/activation telemetry | pass for unknown semantics | Missing token usage remains `null`/unknown. Missing activation evidence remains `unknown`, never zero or false. |

## Probe boundary

[`scripts/probe_cursor_eval.py`](../scripts/probe_cursor_eval.py) is deliberately
standalone. It is not imported by `eval_skills.py`, does not change the current
Codex runner, and cannot create production profiles or durable capability
evidence.

The checked-in, credential-free paths are:

- `preflight` — captures the installed CLI/version, required flags, and fresh-home
  authentication state without a model call;
- `fixtures` — checks valid, model-mismatch, unknown-event, malformed, and partial
  sanitized streams; and
- unit tests — cover strict terminal parsing, exact model comparison, activation
  evidence, judgment validation, timeout, non-zero exit, and output containment.

Run those checks with:

```bash
python3 scripts/probe_cursor_eval.py preflight
python3 scripts/probe_cursor_eval.py fixtures
python3 -m unittest tests.test_probe_cursor_eval
```

The opt-in live path uses a dedicated browser-login template instead of an API
key environment variable:

```bash
python3 scripts/probe_cursor_eval.py bootstrap-auth
python3 scripts/probe_cursor_eval.py live --model <exact-cursor-model-id>
```

`bootstrap-auth` is interactive and must be performed only with the account
owner's approval. The probe refuses a secret-bearing parent environment. Every
prompt, redacted event stream, stderr stream, temporary home, workspace, and
generated artifact remains under `.skill-evals/cursor-cli-probe/`, which is
gitignored. Captured lines are bounded, mode `0600`, and credential-like values
from the dedicated template are replaced before they are written.

The dedicated browser-login template exists only between `bootstrap-auth` and
the next live attempt. Live mode deletes it on success, failure, timeout, or
interruption; failed or interrupted bootstrap also deletes partial credentials.
Copied per-turn credential files are deleted at `system/init` and are also
removed on every earlier failure path. Redacted raw evidence is retained only
until the maintainer reviews the generated capability summary, after which the
entire `.skill-evals/cursor-cli-probe/` directory should be deleted. No
credential-bearing artifact is an accepted retained output.

Live mode performs four fresh turns: positive trigger, near-miss trigger,
behavior containment, and structured judgment. Production eligibility requires
every hard gate to pass. In particular, `unknown` activation, missing telemetry,
missing terminal events, model-display mismatches, secret-canary visibility,
path contamination, timeouts, and malformed output never become a pass.

## Follow-up boundary

This ADR does not define the later adapter registry, migrate Codex, change the
profile schema, implement a Cursor task/judge adapter, or add production
conformance coverage. Those remain the dependent issues under #45. A later
change may update this decision only with a sanitized, exact-version live
summary proving every blocking property.
