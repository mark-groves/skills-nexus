#!/usr/bin/env bash
# Fail-closed aesthetic export via the official draw.io desktop CLI.
# Never falls back to drawio-headless (grey placeholders / wrong layout).
set -euo pipefail

usage() {
  cat <<'EOF' >&2
Usage: export_diagram.sh <input.drawio> <output> [--format svg|png|pdf]

Exports with the official jgraph draw.io desktop CLI under xvfb.
Exits non-zero when drawio/xvfb are missing. Does not use npx
drawio-headless (that path is not valid human-review evidence).

Examples:
  scripts/export_diagram.sh architecture.drawio architecture.review.svg
  scripts/export_diagram.sh architecture.drawio architecture.review.png --format png
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "$#" -lt 2 ]]; then
  usage
  exit 2
fi

input="$1"
output="$2"
shift 2

format=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --format)
      format="${2:-}"
      shift 2
      ;;
    --format=*)
      format="${1#--format=}"
      shift
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${format}" ]]; then
  case "${output}" in
    *.svg) format="svg" ;;
    *.png) format="png" ;;
    *.pdf) format="pdf" ;;
    *)
      echo "ERROR: cannot infer --format from output path; pass --format svg|png|pdf" >&2
      exit 2
      ;;
  esac
fi

case "${format}" in
  svg | png | pdf) ;;
  *)
    echo "ERROR: unsupported format '${format}' (use svg, png, or pdf)" >&2
    exit 2
    ;;
esac

if [[ ! -f "${input}" ]]; then
  echo "ERROR: input diagram not found: ${input}" >&2
  exit 1
fi

if ! command -v drawio >/dev/null 2>&1; then
  cat <<'EOF' >&2
ERROR: official draw.io CLI not found on PATH.

Install with: bash scripts/install-drawio-cli.sh
Do NOT use npx drawio-headless for human-review screenshots — it omits
provider icons and mangles layout. Without drawio, rely on
validate_diagram.py only and report that aesthetic export is unavailable.
EOF
  exit 1
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "ERROR: xvfb-run not found (required for headless Electron export)" >&2
  exit 1
fi

# Refuse wrappers that shadow the official Electron binary.
drawio_path="$(command -v drawio)"
drawio_real="$(readlink -f "${drawio_path}" 2>/dev/null || printf '%s\n' "${drawio_path}")"
case "${drawio_real}" in
  /opt/drawio/* | /opt/draw.io/*) ;;
  *)
    echo "ERROR: '${drawio_path}' (-> ${drawio_real}) is not the official draw.io desktop CLI under /opt/drawio" >&2
    exit 1
    ;;
esac

mkdir -p "$(dirname "${output}")"
tmp_out="${output}.partial.$$"
tmp_svg=""

cleanup() {
  rm -f "${tmp_out}"
  if [[ -n "${tmp_svg}" ]]; then
    rm -f "${tmp_svg}"
  fi
}
trap cleanup EXIT

run_drawio() {
  # --embed-svg-images keeps azure2/aws library glyphs inside SVG exports.
  local fmt="$1"
  local out="$2"
  shift 2
  xvfb-run -a drawio --no-sandbox \
    -x -f "${fmt}" -b 10 \
    "$@" \
    -o "${out}" \
    "${input}"
}

rasterize_embedded_svg() {
  local svg_path="$1"
  local png_path="$2"
  if ! command -v rsvg-convert >/dev/null 2>&1; then
    echo "ERROR: PNG fallback needs rsvg-convert (librsvg2-bin)" >&2
    return 1
  fi
  rsvg-convert -o "${png_path}" "${svg_path}"
}

set +e
case "${format}" in
  svg)
    run_drawio svg "${tmp_out}" --embed-svg-images
    status=$?
    ;;
  png)
    run_drawio png "${tmp_out}"
    status=$?
    if [[ "${status}" -ne 0 || ! -s "${tmp_out}" ]]; then
      # Nested canvases sometimes return Empty export data for PNG while SVG works.
      tmp_svg="${tmp_out}.svg"
      run_drawio svg "${tmp_svg}" --embed-svg-images
      status=$?
      if [[ "${status}" -eq 0 && -s "${tmp_svg}" ]]; then
        rasterize_embedded_svg "${tmp_svg}" "${tmp_out}"
        status=$?
      fi
    fi
    ;;
  pdf)
    run_drawio pdf "${tmp_out}"
    status=$?
    ;;
esac
set -e

if [[ "${status}" -ne 0 || ! -s "${tmp_out}" ]]; then
  echo "ERROR: official draw.io export failed for ${input}" >&2
  exit 1
fi

mv "${tmp_out}" "${output}"
trap - EXIT
if [[ -n "${tmp_svg}" ]]; then
  rm -f "${tmp_svg}"
fi
echo "OK ${output}"
