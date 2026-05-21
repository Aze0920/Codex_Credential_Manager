#!/usr/bin/env bash
# Codex凭证管理 / Codex Credential Console — 一键安装（需 Docker）
set -euo pipefail

# 公开仓库地址：上传 GitHub 后请改成你的仓库，例如：
REPO_URL="${REPO_URL:-https://github.com/Aze0920/Codex_Credential_Manager.git}"
INSTALL_DIR="${INSTALL_DIR:-$(pwd)}"
BRANCH="${BRANCH:-main}"

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] 错误: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "未找到命令: $1"
}

if ! command -v docker >/dev/null 2>&1; then
  die "请先安装 Docker: https://docs.docker.com/engine/install/"
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  die "请安装 Docker Compose 插件或 docker-compose"
fi

if [[ ! -f "$INSTALL_DIR/docker-compose.yml" ]]; then
  need_cmd git
  log "克隆仓库到 $INSTALL_DIR"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" pull --ff-only || true
  else
    mkdir -p "$INSTALL_DIR"
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR.tmp"
    shopt -s dotglob
    mv "$INSTALL_DIR.tmp"/* "$INSTALL_DIR"/
    rmdir "$INSTALL_DIR.tmp"
  fi
fi

cd "$INSTALL_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  log "已创建 .env，请编辑 ADMIN_PASSWORD 后重新执行本脚本或运行: ${COMPOSE[*]} up -d --build"
  die "请先设置 .env 中的 ADMIN_PASSWORD"
fi

if grep -q '^ADMIN_PASSWORD=change-me' .env 2>/dev/null; then
  die "请修改 .env 中的 ADMIN_PASSWORD，不要使用示例密码"
fi

mkdir -p data

log "构建并启动容器..."
"${COMPOSE[@]}" up -d --build

log "完成"
log "前台: http://127.0.0.1:8766"
log "后台: http://127.0.0.1:8766/admin"
log "查看日志: ${COMPOSE[*]} logs -f"
