#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
web_python="${RTL_DEMO_WEB_PYTHON:-$repo_dir/.venv-web/bin/python}"
cd "$repo_dir"
exec "$web_python" -m zerorepo.rtl_web.local "$@"
