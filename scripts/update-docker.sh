#!/usr/bin/env bash
# Docker 部署：在服务器上执行（不是容器里）
set -euo pipefail
INSTALL_DIR="${INSTALL_DIR:-/www/wwwroot/Codex}"
cd "$INSTALL_DIR"

echo "[update-docker] $INSTALL_DIR"
mkdir -p data/backups
if [[ -f data/card_system.db ]]; then
  cp -f data/card_system.db "data/backups/pre-update-$(date +%Y%m%d-%H%M).db"
  echo "[ok] db backup"
fi

git fetch origin main
git reset --hard FETCH_HEAD
echo "[ok] code $(head -1 VERSION 2>/dev/null || echo ?)"

docker compose up -d --build
echo "[ok] container restarted"
echo "[done] open /admin and re-check version"
