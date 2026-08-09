#!/usr/bin/env bash
# Repo-root convenience wrapper; canonical installer lives with cloud-diagram.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT}/plugins/drawio/skills/cloud-diagram/scripts/install-drawio-cli.sh" "$@"
