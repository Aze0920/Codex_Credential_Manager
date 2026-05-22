#!/usr/bin/env bash
# Docker 一键更新：git 同步 + 独立任务容器执行 compose（需容器内 docker CLI + docker.sock）
set -u

DIR="${HOST_INSTALL_DIR:-${INSTALL_DIR:-/host-codex}}"
LOG="${UPDATE_LOG_FILE:-$DIR/data/update-latest.log}"
JOB_NAME="codex-update-job"
MAIN_CONTAINER="codex-credential-manager"

log_line() { echo "$*" >>"$LOG"; }
fail() { log_line "[error] $*"; echo "[error] $*"; exit 1; }
progress() { log_line "[progress] $1|$2"; echo "[progress] $1|$2"; }

mkdir -p "$(dirname "$LOG")" "$DIR/data/backups"
: >"$LOG"
progress 2 "开始更新"

log_line "[update-docker] DIR=$DIR"
echo "[update-docker] DIR=$DIR"

if [[ ! -d "$DIR" ]]; then
  fail "项目目录不存在: $DIR（需挂载 .:/host-codex）"
fi
if [[ ! -d "$DIR/.git" ]]; then
  fail "不是 git 仓库: $DIR"
fi
if [[ ! -S /var/run/docker.sock ]]; then
  fail "未挂载 /var/run/docker.sock"
fi
if [[ ! -f "$DIR/docker-compose.yml" ]]; then
  fail "缺少 docker-compose.yml"
fi

DOCKER_BIN=""
for candidate in /usr/local/bin/docker /usr/bin/docker docker; do
  if [[ -x "$candidate" ]] || command -v "$candidate" >/dev/null 2>&1; then
    DOCKER_BIN="$(command -v "$candidate" 2>/dev/null || echo "$candidate")"
    break
  fi
done
COMPOSE_BIN=""
if [[ -x /usr/local/bin/docker-compose ]]; then
  COMPOSE_BIN="/usr/local/bin/docker-compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN="$(command -v docker-compose)"
fi
if [[ -z "$DOCKER_BIN" ]]; then
  fail "未找到 docker 命令（请重建镜像以安装 docker CLI）"
fi
if [[ -z "$COMPOSE_BIN" ]]; then
  fail "未找到 docker-compose"
fi

cd "$DIR" || fail "无法进入 $DIR"

if [[ -f data/card_system.db ]]; then
  cp -f data/card_system.db "data/backups/pre-update-$(date +%Y%m%d-%H%M).db" || true
  progress 8 "数据库已备份"
fi

progress 12 "正在从 GitHub 拉取代码"
git config --global --add safe.directory "$DIR" 2>/dev/null || true
if ! git fetch origin main >>"$LOG" 2>&1; then
  fail "git fetch 失败（请检查服务器能否访问 GitHub）"
fi
if ! git reset --hard FETCH_HEAD >>"$LOG" 2>&1; then
  fail "git reset 失败"
fi
VER="$(head -1 VERSION 2>/dev/null || echo ?)"
progress 45 "代码已同步到 v${VER}"
log_line "[ok] code $VER"

export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

"$DOCKER_BIN" rm -f "$JOB_NAME" "$MAIN_CONTAINER" >>"$LOG" 2>&1 || true
progress 50 "已移除旧容器，准备重建"
progress 52 "正在提交容器重建（主服务会短暂断开，请稍候）"
log_line "[ok] docker=$DOCKER_BIN compose=$COMPOSE_BIN"

# 用 alpine + 挂载 docker/compose 二进制，避免拉取 docker:26-cli 失败
if ! "$DOCKER_BIN" run -d --name "$JOB_NAME" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$DIR:/work" \
  -v "$DOCKER_BIN:/usr/local/bin/docker:ro" \
  -v "$COMPOSE_BIN:/usr/local/bin/docker-compose:ro" \
  -w /work \
  -e DOCKER_HOST=unix:///var/run/docker.sock \
  -e COMPOSE_PROJECT_NAME=codex \
  alpine:3.20 \
  sh -c '
    set -u
    LOG=/work/data/update-latest.log
    echo "[progress] 55|清理旧容器" >> "$LOG"
    /usr/local/bin/docker rm -f codex-update-job codex-credential-manager 2>>"$LOG" || true
    /usr/local/bin/docker-compose -f /work/docker-compose.yml -p codex down --remove-orphans 2>>"$LOG" || true
    echo "[progress] 60|Docker 正在 build / 启动" >> "$LOG"
    if /usr/local/bin/docker-compose -f /work/docker-compose.yml -p codex up -d --build --force-recreate --remove-orphans >>"$LOG" 2>&1; then
      echo "[progress] 95|容器已启动" >> "$LOG"
      echo "[done] ok" >> "$LOG"
      exit 0
    fi
    echo "[error] docker compose up 失败" >> "$LOG"
    exit 1
  ' >>"$LOG" 2>&1; then
  fail "无法启动重建任务（请确认能拉取 alpine:3.20 或 SSH 手动 docker compose up）"
fi

progress 58 "重建任务已提交，等待新容器就绪…"
log_line "[ok] job $JOB_NAME started"

deadline=$((SECONDS + 540))
while (( SECONDS < deadline )); do
  if ! "$DOCKER_BIN" ps -q -f "name=^${JOB_NAME}$" 2>/dev/null | grep -q .; then
    if grep -q '\[done\]' "$LOG" 2>/dev/null; then
      progress 100 "更新完成"
      log_line "[done] finished"
      exit 0
    fi
    if grep -q '\[error\]' "$LOG" 2>/dev/null; then
      fail "重建失败（见日志）"
    fi
    sleep 2
    continue
  fi
  sleep 3
done

fail "等待重建超时（9 分钟），请 SSH 查看 data/update-latest.log"
