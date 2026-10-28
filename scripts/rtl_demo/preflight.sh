#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ ! -d "$repo_dir/zerorepo" ]]; then
    repo_dir=/opt/rtl-agent/current
fi
[[ -d "$repo_dir/zerorepo" ]] || { echo 'Runtime release is not prepared.' >&2; exit 4; }
web_python="${RTL_DEMO_WEB_PYTHON:-$repo_dir/.venv-web/bin/python}"
cd "$repo_dir"
export PYTHONPATH="$repo_dir"
exec "$web_python" -m zerorepo.rtl_web.cli preflight --config "${RTL_DEMO_CONFIG:-$repo_dir/configs/rtl_demo.example.yaml}" --json "$@"
