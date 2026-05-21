#!/usr/bin/env bash
# Codex凭证管理 — 从 GitHub 拉取代码并重启（CentOS 7 pyenv + systemd）
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/www/wwwroot/Codex}"
SERVICE_NAME="${SERVICE_NAME:-codex-web}"
PYENV_ROOT="${PYENV_ROOT:-/root/.pyenv}"

log() { printf '[update] %s\n' "$*"; }

if [[ ! -d "$INSTALL_DIR" ]]; then
  log "目录不存在: $INSTALL_DIR"
  exit 1
fi

cd "$INSTALL_DIR"

if [[ -d .git ]]; then
  log "git pull"
  git pull --ff-only
else
  log "警告: 非 git 目录，请手动上传或 git clone"
  exit 1
fi

export PYENV_ROOT
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv >/dev/null 2>&1; then
  eval "$(pyenv init - bash)"
fi

if command -v python >/dev/null 2>&1; then
  python -m pip install -r requirements.txt -q
fi

log "备份数据库"
python - <<'PY' || true
from core.db_config import create_database_backup
try:
    path = create_database_backup()
    print("backup:", path)
except Exception as exc:
    print("backup skipped:", exc)
PY

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
  log "重启 $SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
else
  log "未检测到 systemd 服务 $SERVICE_NAME，请手动重启进程"
fi

log "完成。当前版本:"
cat VERSION 2>/dev/null || true
