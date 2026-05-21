#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt
python tools/session_converter_web.py --host "${HOST:-0.0.0.0}" --port "${PORT:-8766}"
