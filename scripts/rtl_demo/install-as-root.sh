#!/usr/bin/env bash
set -euo pipefail
# Usage: install-as-root.sh RELEASE [--dry-run]
#        install-as-root.sh --rollback BACKUP [--dry-run]
# Only design static files. Never modifies Caddyfile, services or main/www.
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/release.py" install "$@"
