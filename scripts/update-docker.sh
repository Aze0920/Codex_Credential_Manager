#!/usr/bin/env bash
# Docker 一键更新：git 同步 + 独立容器执行 compose（避免重建时杀掉本进程）
set -u

DIR="${HOST_INSTALL_DIR:-${INSTALL_DIR:-/host-codex}}"
LOG="${UPDATE_LOG_FILE:-$DIR/data/update-latest.log}"
JOB_NAME="codex-update-job"
fail() { echo "[error] $*"; echo "[error] $*" >>"$LOG"; exit 1; }
progress() { echo "[progress] $1|$2"; echo "[progress] $1|$2" >>"$LOG"; }

mkdir -p "$(dirname "$LOG")" "$DIR/data/backups"
: >"$LOG"
progress 2 "开始更新"

echo "[update-docker] DIR=$DIR" | tee -a "$LOG"

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
# 必须用 FETCH_HEAD：仅 fetch 分支时 origin/main 可能仍是旧提交
if ! git reset --hard FETCH_HEAD >>"$LOG" 2>&1; then
  fail "git reset 失败"
fi
VER="$(head -1 VERSION 2>/dev/null || echo ?)"
progress 45 "代码已同步到 v${VER}"
echo "[ok] code $VER" >>"$LOG"

export DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"
COMPOSE_BIN=""
if [[ -x /usr/local/bin/docker-compose ]]; then
  COMPOSE_BIN="/usr/local/bin/docker-compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN="$(command -v docker-compose)"
fi
if [[ -z "$COMPOSE_BIN" ]]; then
  fail "未找到 docker-compose（请重建镜像）"
fi

MAIN_CONTAINER="codex-credential-manager"
docker rm -f "$JOB_NAME" "$MAIN_CONTAINER" >>"$LOG" 2>&1 || true
progress 50 "已移除旧容器，准备重建"
progress 52 "正在提交容器重建（主服务会短暂断开，请稍候）"
echo "[ok] compose bin=$COMPOSE_BIN" >>"$LOG"

if ! docker run -d --name "$JOB_NAME" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$DIR:/work" \
  -v "$COMPOSE_BIN:/usr/local/bin/docker-compose:ro" \
  -w /work \
  -e DOCKER_HOST=unix:///var/run/docker.sock \
  -e COMPOSE_PROJECT_NAME=codex \
  docker:26-cli \
  sh -c '
    set -u
    MAIN=codex-credential-manager
    JOB=codex-update-job
    LOG=/work/data/update-latest.log
    echo "[progress] 55|清理旧容器" >> "$LOG"
    docker rm -f "$JOB" "$MAIN" 2>>"$LOG" || true
    /usr/local/bin/docker-compose -f /work/docker-compose.yml down --remove-orphans 2>>"$LOG" || true
    echo "[progress] 60|Docker 正在 build / 启动" >> "$LOG"
    if /usr/local/bin/docker-compose -f /work/docker-compose.yml up -d --build --force-recreate --remove-orphans >>"$LOG" 2>&1; then
      echo "[progress] 95|容器已启动" >> "$LOG"
      echo "[done] ok" >> "$LOG"
      exit 0
    fi
    echo "[error] docker compose up 失败（若提示容器名冲突，请 SSH 执行: docker rm -f codex-credential-manager）" >> "$LOG"
    exit 1
  ' >>"$LOG" 2>&1; then
  fail "无法启动重建任务容器（可能无法拉取 docker:26-cli 镜像）"
fi

progress 58 "重建任务已提交，等待新容器就绪…"
echo "[ok] job $JOB_NAME started" >>"$LOG"

# 轮询 sidecar 日志直到结束或超时（本脚本在旧容器内，可能中途被杀）
deadline=$((SECONDS + 540))
while (( SECONDS < deadline )); do
  if ! docker ps -q -f "name=^${JOB_NAME}$" | grep -q .; then
    if grep -q '\[done\]' "$LOG" 2>/dev/null; then
      progress 100 "更新完成"
      echo "[done] finished" >>"$LOG"
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

fail "等待重建超时（9 分钟），请 SSH 查看 docker logs / data/update-latest.log"
