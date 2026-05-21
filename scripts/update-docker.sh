#!/usr/bin/env bash
# Docker 一键更新（容器内执行，操作宿主机项目 + docker.sock）
set -u

DIR="${HOST_INSTALL_DIR:-${INSTALL_DIR:-/host-codex}}"
fail() { echo "[error] $*"; exit 1; }

echo "[update-docker] start"
echo "[update-docker] DIR=$DIR"

if [[ ! -d "$DIR" ]]; then
  fail "项目目录不存在: $DIR。请重建容器并挂载 .:/host-codex（见 docker-compose.yml）"
fi
if [[ ! -d "$DIR/.git" ]]; then
  fail "不是 git 仓库: $DIR"
fi
if [[ ! -S /var/run/docker.sock ]]; then
  fail "未挂载 /var/run/docker.sock，无法重建容器"
fi
if [[ ! -f "$DIR/docker-compose.yml" ]]; then
  fail "缺少 docker-compose.yml: $DIR"
fi

cd "$DIR" || fail "无法进入 $DIR"

mkdir -p data/backups
if [[ -f data/card_system.db ]]; then
  cp -f data/card_system.db "data/backups/pre-update-$(date +%Y%m%d-%H%M).db" || true
  echo "[ok] db backup"
fi

git config --global --add safe.directory "$DIR" 2>/dev/null || true
if ! git fetch origin main 2>&1; then
  fail "git fetch 失败，请检查服务器能否访问 GitHub"
fi
if ! git reset --hard FETCH_HEAD 2>&1; then
  fail "git reset 失败"
fi
echo "[ok] code $(head -1 VERSION 2>/dev/null || echo ?)"

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
  else
    fail "未找到 docker compose 命令"
  fi
else
  fail "容器内未安装 docker 命令"
fi

echo "[ok] using $DC"
if ! $DC -f "$DIR/docker-compose.yml" up -d --build 2>&1; then
  fail "docker compose up 失败"
fi

echo "[ok] container restarted"
echo "[done]"
