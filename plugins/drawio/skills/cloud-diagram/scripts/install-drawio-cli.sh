#!/usr/bin/env bash
# Install the official jgraph draw.io desktop CLI for aesthetic diagram export.
# Idempotent: skips the .deb install when the pinned official binary is present.
# Bundled with cloud-diagram so deployed skills can bootstrap without the repo.
set -euo pipefail

DRAWIO_VERSION="${DRAWIO_VERSION:-31.1.5}"
DRAWIO_DEB="drawio-amd64-${DRAWIO_VERSION}.deb"
DRAWIO_URL="https://github.com/jgraph/drawio-desktop/releases/download/v${DRAWIO_VERSION}/${DRAWIO_DEB}"
# Pin the upstream .deb so a poisoned cache/path cannot be installed.
DRAWIO_SHA256="${DRAWIO_SHA256:-93c2d86e418d120179b547409e5a1d3f5fba58f409b033077206cca96a5edc3d}"
MARKER="/usr/local/share/drawio-cli.version"

if [[ ! "${DRAWIO_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: DRAWIO_VERSION must be MAJOR.MINOR.PATCH (got '${DRAWIO_VERSION}')" >&2
  exit 1
fi
if [[ ! "${DRAWIO_SHA256}" =~ ^[a-fA-F0-9]{64}$ ]]; then
  echo "ERROR: DRAWIO_SHA256 must be a 64-char hex digest" >&2
  exit 1
fi

need_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

install_apt_deps() {
  export DEBIAN_FRONTEND=noninteractive
  need_root apt-get update -y
  need_root apt-get install -y --no-install-recommends \
    xvfb \
    libgbm1 \
    libasound2t64 \
    librsvg2-bin \
    ca-certificates \
    curl
}

official_drawio_bin() {
  local candidate drawio_path drawio_real
  for candidate in /opt/drawio/drawio /opt/draw.io/drawio; do
    if [[ -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  if ! command -v drawio >/dev/null 2>&1; then
    return 1
  fi
  drawio_path="$(command -v drawio)"
  drawio_real="$(readlink -f "${drawio_path}" 2>/dev/null || printf '%s\n' "${drawio_path}")"
  case "${drawio_real}" in
    /opt/drawio/* | /opt/draw.io/*)
      printf '%s\n' "${drawio_real}"
      return 0
      ;;
    *) return 1 ;;
  esac
}

is_official_drawio() {
  official_drawio_bin >/dev/null
}

run_drawio_version() {
  local bin
  bin="$(official_drawio_bin)" || return 1
  # Electron needs a display on headless agents; prefer xvfb when available.
  if command -v xvfb-run >/dev/null 2>&1; then
    xvfb-run -a "${bin}" --no-sandbox --version 2>/dev/null
  else
    "${bin}" --no-sandbox --version 2>/dev/null
  fi
}

# Always probe the official binary (never trust MARKER alone — it can go stale).
# Electron may dump dbus noise on stdout before the real "31.1.5" line.
probe_installed_version() {
  is_official_drawio || return 1
  run_drawio_version | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

write_version_marker() {
  # Avoid embedding env values in a root `bash -c` string (CWE-78).
  printf '%s\n' "${DRAWIO_VERSION}" | need_root tee "${MARKER}" >/dev/null
}

# Repair partial hosts before any version shortcut (xvfb + PNG fallback).
if ! command -v xvfb-run >/dev/null 2>&1 || ! command -v rsvg-convert >/dev/null 2>&1; then
  install_apt_deps
fi

installed="$(probe_installed_version || true)"
if [[ "${installed}" == "${DRAWIO_VERSION}" ]]; then
  echo "draw.io CLI ${DRAWIO_VERSION} already installed (official binary)"
else
  if ! command -v curl >/dev/null 2>&1; then
    install_apt_deps
  fi

  # Private mktemp dir — never install from a shared world-writable cache.
  cache_dir="$(mktemp -d "${TMPDIR:-/tmp}/drawio-cli.XXXXXX")"
  cleanup_cache() {
    rm -rf "${cache_dir}"
  }
  trap cleanup_cache EXIT

  deb_path="${cache_dir}/${DRAWIO_DEB}"
  curl -fsSL --retry 5 --retry-delay 2 -o "${deb_path}.partial" "${DRAWIO_URL}"
  mv "${deb_path}.partial" "${deb_path}"

  actual_sha256="$(sha256sum "${deb_path}" | awk '{print $1}')"
  if [[ "${actual_sha256}" != "${DRAWIO_SHA256}" ]]; then
    echo "ERROR: draw.io .deb SHA-256 mismatch" >&2
    echo "  expected: ${DRAWIO_SHA256}" >&2
    echo "  actual:   ${actual_sha256}" >&2
    exit 1
  fi

  need_root apt-get install -y "${deb_path}"
  write_version_marker
  echo "Installed draw.io CLI ${DRAWIO_VERSION}"

  trap - EXIT
  cleanup_cache
fi

if ! is_official_drawio; then
  echo "ERROR: official draw.io binary under /opt/drawio missing after install" >&2
  exit 1
fi
if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "ERROR: xvfb-run missing after install" >&2
  exit 1
fi
if ! command -v rsvg-convert >/dev/null 2>&1; then
  echo "ERROR: rsvg-convert missing after install (needed for PNG fallback)" >&2
  exit 1
fi

# Warn when PATH is shadowed by a non-official drawio (exporter rejects that).
if command -v drawio >/dev/null 2>&1; then
  path_drawio="$(command -v drawio)"
  path_real="$(readlink -f "${path_drawio}" 2>/dev/null || printf '%s\n' "${path_drawio}")"
  case "${path_real}" in
    /opt/drawio/* | /opt/draw.io/*) ;;
    *)
      echo "WARNING: PATH drawio '${path_drawio}' (-> ${path_real}) shadows the official CLI; export_diagram.sh will reject it" >&2
      ;;
  esac
fi

# Smoke: binary under xvfb must report the pinned version exactly.
probed="$(probe_installed_version || true)"
if [[ "${probed}" != "${DRAWIO_VERSION}" ]]; then
  echo "ERROR: draw.io version probe mismatch (expected ${DRAWIO_VERSION}, got '${probed:-<empty>}')" >&2
  exit 1
fi
echo "draw.io CLI ready: ${probed} ($(official_drawio_bin))"
