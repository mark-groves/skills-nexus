#!/usr/bin/env bash
# Install the official jgraph draw.io desktop CLI for aesthetic diagram export.
# Idempotent: skips download when the pinned version is already on PATH.
set -euo pipefail

DRAWIO_VERSION="${DRAWIO_VERSION:-31.1.5}"
DRAWIO_DEB="drawio-amd64-${DRAWIO_VERSION}.deb"
DRAWIO_URL="https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/${DRAWIO_DEB}"
CACHE_DIR="${DRAWIO_CACHE_DIR:-${TMPDIR:-/tmp}/drawio-cli}"
MARKER="/usr/local/share/drawio-cli.version"

need_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

current_version() {
  if ! command -v drawio >/dev/null 2>&1; then
    return 1
  fi
  # drawio --version prints like "31.1.5" (sometimes with extra noise).
  drawio --no-sandbox --version 2>/dev/null | head -n 1 | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

installed="$(current_version || true)"
if [[ "${installed}" == "${DRAWIO_VERSION}" ]]; then
  echo "draw.io CLI ${DRAWIO_VERSION} already installed"
else
  export DEBIAN_FRONTEND=noninteractive
  need_root apt-get update -y
  need_root apt-get install -y --no-install-recommends \
    xvfb \
    libgbm1 \
    libasound2t64 \
    librsvg2-bin \
    ca-certificates \
    curl

  mkdir -p "${CACHE_DIR}"
  deb_path="${CACHE_DIR}/${DRAWIO_DEB}"
  if [[ ! -f "${deb_path}" ]]; then
    curl -fsSL --retry 5 --retry-delay 2 -o "${deb_path}.partial" "${DRAWIO_URL}"
    mv "${deb_path}.partial" "${deb_path}"
  fi
  need_root apt-get install -y "${deb_path}"
  need_root bash -c "printf '%s\n' '${DRAWIO_VERSION}' > '${MARKER}'"
  echo "Installed draw.io CLI ${DRAWIO_VERSION}"
fi

if ! command -v drawio >/dev/null 2>&1; then
  echo "ERROR: drawio binary missing after install" >&2
  exit 1
fi
if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "ERROR: xvfb-run missing after install" >&2
  exit 1
fi

# Smoke: version must resolve under xvfb (Electron needs a display).
xvfb-run -a drawio --no-sandbox --version >/dev/null
echo "draw.io CLI ready: $(drawio --no-sandbox --version 2>/dev/null | head -n 1)"
