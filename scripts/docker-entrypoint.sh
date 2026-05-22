#!/bin/sh
# 启动时自动把宿主机 VERSION 同步到 /app（与 git pull / 一键更新对齐）
set -e
if [ -f /host-codex/VERSION ]; then
  cp -f /host-codex/VERSION /app/VERSION 2>/dev/null || true
fi
cd /app || exit 1
exec python3 tools/session_converter_web.py --host "${HOST:-0.0.0.0}" --port "${PORT:-8766}"
