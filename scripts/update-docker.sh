#!/bin/sh
# 在独立容器 codex-update-job 中执行（由后台 API 启动，不占用 Web 容器进程）
# 顺序：git pull → compose 重建 → 健康检查
set -eu

DIR="${HOST_INSTALL_DIR:-/work}"
LOG="${UPDATE_LOG_FILE:-$DIR/data/update-latest.log}"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-codex}"

log() { echo "$*" >>"$LOG"; }
progress() { log "[progress] $1|$2"; }
fail() { log "[error] $*"; exit 1; }

mkdir -p "$(dirname "$LOG")" "$DIR/data/backups"
: >"$LOG"
progress 2 "更新任务已启动"
log "[update-docker] runner=$(hostname) DIR=$DIR"

if [ ! -d "$DIR/.git" ]; then fail "不是 git 仓库: $DIR"; fi
if [ ! -S /var/run/docker.sock ]; then fail "未挂载 docker.sock"; fi
if [ ! -f "$DIR/docker-compose.yml" ]; then fail "缺少 docker-compose.yml"; fi
if [ ! -x /usr/local/bin/docker-compose ]; then fail "未挂载 docker-compose"; fi

export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
export GIT_TERMINAL_PROMPT=0

if ! command -v git >/dev/null 2>&1 || ! command -v wget >/dev/null 2>&1; then
  progress 5 "安装 git、wget…"
  apk add --no-cache git wget >/dev/null 2>&1 || fail "无法安装依赖"
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

# 先 build、后切换：避免 compose down 导致长时间 502（旧容器在 build 期间仍在线）
progress 52 "后台构建镜像（旧服务仍在运行，此阶段无 502）"
export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1
log "[build] docker compose build codex-web"
if ! /usr/local/bin/docker-compose -f docker-compose.yml -p "$COMPOSE_PROJECT" build codex-web >>"$LOG" 2>&1; then
  fail "镜像构建失败"
fi

progress 72 "切换新容器（约 10–40 秒 502，属正常）"
log "[up] docker compose up codex-web --force-recreate"
if ! /usr/local/bin/docker-compose -f docker-compose.yml -p "$COMPOSE_PROJECT" up -d --no-deps --force-recreate codex-web >>"$LOG" 2>&1; then
  fail "容器启动失败"
fi

progress 88 "等待新服务就绪"
ok=0
i=0
while [ "$i" -lt 60 ]; do
  if wget -qO- http://127.0.0.1:8766/api/admin/health 2>/dev/null | grep -q '"ok"'; then
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
