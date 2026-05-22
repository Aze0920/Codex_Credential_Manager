#!/bin/sh
# 在独立容器 codex-update-job 中执行（由后台 API 启动，不占用 Web 容器进程）
set -eu

DIR="${HOST_INSTALL_DIR:-/work}"
LOG="${UPDATE_LOG_FILE:-$DIR/data/update-latest.log}"
MAIN_CONTAINER="codex-credential-manager"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-codex}"

log() { echo "$*" >>"$LOG"; }
progress() { log "[progress] $1|$2"; }
fail() { log "[error] $*"; exit 1; }

# 去掉 Windows CRLF，避免 /bin/sh^M 秒退
if [ -f "$DIR/scripts/update-docker.sh" ]; then
  sed -i 's/\r$//' "$DIR/scripts/update-docker.sh" 2>/dev/null || true
fi

mkdir -p "$(dirname "$LOG")" "$DIR/data/backups"
log "[progress] 2|更新任务已启动"
log "[update-docker] runner=$(hostname) DIR=$DIR"

if [ ! -d "$DIR/.git" ]; then fail "不是 git 仓库: $DIR"; fi
if [ ! -S /var/run/docker.sock ]; then fail "未挂载 docker.sock"; fi
if [ ! -f "$DIR/docker-compose.yml" ]; then fail "缺少 docker-compose.yml"; fi

export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
export GIT_TERMINAL_PROMPT=0

compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose -f "$DIR/docker-compose.yml" -p "$COMPOSE_PROJECT" "$@"
    return
  fi
  if [ -f /usr/local/bin/docker-compose ]; then
    /usr/local/bin/docker-compose -f "$DIR/docker-compose.yml" -p "$COMPOSE_PROJECT" "$@"
    return
  fi
  fail "未找到 docker compose（请确认 docker.sock 与 docker CLI 可用）"
}

if ! command -v git >/dev/null 2>&1; then
  progress 5 "安装 git…"
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache git >>"$LOG" 2>&1 || fail "无法安装 git"
  else
    fail "容器内无 git，请使用 docker:27-cli 镜像"
  fi
fi

if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
  command -v apk >/dev/null 2>&1 && apk add --no-cache curl >>"$LOG" 2>&1 || true
fi

cd "$DIR" || fail "无法进入 $DIR"

if [ -f data/card_system.db ]; then
  cp -f data/card_system.db "data/backups/pre-update-$(date +%Y%m%d-%H%M).db" 2>/dev/null || true
  progress 8 "数据库已备份"
fi

rm -f .git/index.lock .git/shallow.lock 2>/dev/null || true
git config --global --add safe.directory "$DIR" 2>/dev/null || true

progress 12 "正在同步 GitHub 代码"
log "[git] fetch origin main"
if ! git fetch origin main >>"$LOG" 2>&1; then
  fail "git fetch 失败，请查看日志"
fi
if ! git reset --hard origin/main >>"$LOG" 2>&1; then
  fail "git reset 失败"
fi
VER="$(head -1 VERSION 2>/dev/null || echo ?)"
progress 45 "代码已同步到 v${VER}"
log "[ok] synced $VER"

# Docker 在挂载不存在的文件时会创建同名目录，导致 ./VERSION 类挂载失败
if [ -d "$DIR/VERSION" ]; then
  ver="$(cat "$DIR/VERSION/VERSION" 2>/dev/null || echo "")"
  rm -rf "$DIR/VERSION"
  log "[fix] 已删除误建的 VERSION 目录"
  if [ -n "$ver" ]; then echo "$ver" >"$DIR/VERSION"; fi
fi
if [ ! -f "$DIR/VERSION" ]; then
  echo "0.0.0" >"$DIR/VERSION"
  log "[fix] 已创建 VERSION 文件"
fi

progress 50 "停止旧容器"
compose_cmd down --remove-orphans >>"$LOG" 2>&1 || true
docker rm -f "$MAIN_CONTAINER" >>"$LOG" 2>&1 || true

progress 60 "正在 build 并启动（请耐心等待）"
if ! compose_cmd up -d --build --force-recreate --remove-orphans >>"$LOG" 2>&1; then
  fail "docker compose up 失败"
fi

progress 92 "等待服务就绪"
ok=0
i=0
while [ "$i" -lt 60 ]; do
  if curl -sf "http://127.0.0.1:8766/api/admin/health" 2>/dev/null | grep -q '"ok"'; then
    ok=1
    break
  fi
  if wget -qO- "http://127.0.0.1:8766/api/admin/health" 2>/dev/null | grep -q '"ok"'; then
    ok=1
    break
  fi
  i=$((i + 1))
  sleep 2
done

if [ "$ok" -ne 1 ]; then
  fail "健康检查超时，请执行: docker compose -p $COMPOSE_PROJECT ps"
fi

progress 100 "更新完成"
log "[done] ok"
exit 0
