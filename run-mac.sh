#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[错误] 未找到: $1"
    exit 1
  }
}

need python3
need node

PY_VER="$(python3 -c 'import sys; print(sys.version_info >= (3, 10))')"
if [[ "$PY_VER" != "True" ]]; then
  echo "[错误] 需要 Python 3.10+，当前: $(python3 --version)"
  exit 1
fi

NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
if [[ "$NODE_MAJOR" -lt 16 ]]; then
  echo "[错误] 需要 Node.js 16+，当前: $(node --version)"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "[提示] 创建虚拟环境 .venv ..."
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate
pip install -r requirements.txt -q

mkdir -p data

export ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"
export NODE_EXECUTABLE="${NODE_EXECUTABLE:-$(command -v node)}"

echo ""
echo "前台: http://127.0.0.1:8766"
echo "后台: http://127.0.0.1:8766/admin"
echo "按 Ctrl+C 停止"
echo ""

python3 tools/session_converter_web.py --host 127.0.0.1 --port 8766
