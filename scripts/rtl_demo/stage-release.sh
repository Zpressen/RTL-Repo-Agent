#!/usr/bin/env bash
set -euo pipefail
# Usage: stage-release.sh DIST STAGING_RELEASES RELEASE_ID [--dry-run]
# STAGING_RELEASES on gateway: /home/dev/deepvalleychip-site/releases
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/release.py" stage "$@"
