#!/usr/bin/env bash
# Download one pinned draw.io sidebar file. Fails closed: a gh error, an empty
# body, or a hash mismatch exits non-zero and leaves any existing copy intact.
set -euo pipefail

PIN="24b76c2cbd55d88e354042e8d329a2e4708972bc"
SIDEBAR_DIR="src/main/webapp/js/diagramly/sidebar"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
default_dest="$(cd "${script_dir}/.." && pwd)/working"

if [[ "${1:-}" == "--input-file" ]]; then
  if [[ "$#" -ne 2 ]]; then
    echo "Usage: fetch_sidebar.sh --input-file sidebar-request.json" >&2
    exit 2
  fi
  # The basename is allowlisted by sidebar_names.py before it reaches the shell.
  file="$(python3 "${script_dir}/sidebar_names.py" emit-fetch-request "${2}")"
  dest="${default_dest}"
elif [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
  echo "Usage: fetch_sidebar.sh Sidebar-AWS4.js [dest-dir]" >&2
  echo "       fetch_sidebar.sh --input-file sidebar-request.json" >&2
  exit 2
else
  file="$1"
  dest="${2:-${default_dest}}"
fi
if [[ ! "${file}" =~ ^Sidebar-[A-Za-z0-9]+\.js$ ]]; then
  echo "ERROR: expected a sidebar file name like Sidebar-AWS4.js (got '${file}')" >&2
  exit 2
fi
mkdir -p "${dest}"

# Empty GH_TOKEN keeps a broken local token from poisoning anonymous reads.
sha="$(env GH_TOKEN= gh api "repos/jgraph/drawio/contents/${SIDEBAR_DIR}/${file}?ref=${PIN}" -q '.sha')"
if [[ ! "${sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: no blob SHA for ${file} at ${PIN} (got '${sha}')" >&2
  exit 1
fi

tmp="$(mktemp "${dest}/.${file}.XXXXXX")"
trap 'rm -f "${tmp}"' EXIT
env GH_TOKEN= gh api "repos/jgraph/drawio/git/blobs/${sha}" -q '.content' | base64 -d >"${tmp}"

actual="$(git hash-object "${tmp}")"
if [[ "${actual}" != "${sha}" ]]; then
  echo "ERROR: downloaded ${file} does not match blob ${sha} (got ${actual})" >&2
  exit 1
fi
mv "${tmp}" "${dest}/${file}"
trap - EXIT
echo "OK ${dest}/${file} (${sha})"
