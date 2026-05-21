#!/usr/bin/env bash
# Docker 一键更新：在容器内调用宿主机 docker（需挂载 docker.sock 与项目目录）
set -euo pipefail
DIR="${HOST_INSTALL_DIR:-${INSTALL_DIR:-/www/wwwroot/Codex}}"
cd "$DIR"

echo "[update-docker] $DIR"
mkdir -p data/backups
if [[ -f data/card_system.db ]]; then
  cp -f data/card_system.db "data/backups/pre-update-$(date +%Y%m%d-%H%M).db"
  echo "[ok] db backup"
fi

git fetch origin main
git reset --hard FETCH_HEAD
echo "[ok] code $(head -1 VERSION 2>/dev/null || echo ?)"

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] docker CLI not found in container"
  exit 1
fi

docker compose -f "$DIR/docker-compose.yml" up -d --build
echo "[ok] container restarted"
echo "[done]"
