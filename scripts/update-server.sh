#!/usr/bin/env bash
# Codex 服务器更新（pyenv + systemd），不删除 data/card_system.db
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/www/wwwroot/Codex}"
cd "$INSTALL_DIR"

echo "[update] dir=$INSTALL_DIR"

if [[ ! -f data/card_system.db ]]; then
  echo "[warn] data/card_system.db not found"
else
  mkdir -p data/backups
  cp -f data/card_system.db "data/backups/pre-update-$(date +%Y%m%d-%H%M).db"
  echo "[ok] db backed up"
fi

if [[ -d .git ]]; then
  git fetch origin main
  git reset --hard FETCH_HEAD
  echo "[ok] code updated from GitHub"
else
  echo "[error] not a git repo: $INSTALL_DIR"
  exit 1
fi

export PYENV_ROOT="${PYENV_ROOT:-/root/.pyenv}"
export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
if command -v pyenv >/dev/null 2>&1; then
  eval "$(pyenv init - bash)"
fi

pip install -r requirements.txt -q
echo "[ok] pip install done"

if systemctl is-active --quiet codex-web 2>/dev/null; then
  systemctl restart codex-web
  echo "[ok] codex-web restarted"
else
  echo "[warn] codex-web not running via systemd"
fi

echo "[done] update finished"
