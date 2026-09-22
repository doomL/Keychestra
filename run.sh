#!/usr/bin/env bash
# Quick launcher for OrganBgWorker
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then
  python3 -m venv --system-site-packages .venv
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python -m organ_bg "$@"
