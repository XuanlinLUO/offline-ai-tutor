#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m backend.app "$@"
else
  exec python3 -m backend.app "$@"
fi
