# 服务器部署指南（CentOS 7 裸机 · pyenv）

适用于 **宝塔 / 云服务器 CentOS 7**，系统自带 **Python 2.7**、无 `python3` 的情况。  
这是你当前在用的安装方式（pyenv 编译 Python 3.11 + systemd 后台运行）。

> **新机推荐 Docker**：见 [DEPLOY.md](DEPLOY.md) 或 README 的 Docker 章节。  
> **已有本方式跑起来的服务器**：用本文「日常维护」和「更新代码」即可。

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 系统 | CentOS 7.x（64 位） |
| 内存 | 建议 ≥ 1GB |
| 磁盘 | 项目 + pyenv 编译约需 2GB 临时空间 |
| 端口 | **8766**（防火墙 / 安全组 / 宝塔放行） |
| Node | **16+**（宝塔 nvm 常见路径见下文） |

---

## 第 0 步：上传代码

将项目放到例如：

```text
/www/wwwroot/Codex
```

可用 Git、宝塔文件管理、SFTP。**不要**上传 `data/*.db`、`.env`、`.venv`。

---

## 第 1 步：安装编译依赖

```bash
yum install -y gcc make patch zlib-devel bzip2 bzip2-devel readline-devel \
  sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel git curl
```

---

## 第 2 步：安装 OpenSSL 1.1（Python 3.11 必需）

CentOS 7 自带 OpenSSL 1.0，不装此项 pyenv 编译会报 `_ssl` / `ModuleNotFoundError`。

```bash
yum install -y openssl11 openssl11-devel openssl11-libs --disablerepo=centos-sclo-sclo
```

检查：

```bash
pkg-config --cflags --libs openssl11
ls /usr/include/openssl11/openssl/ssl.h
```

---

## 第 3 步：安装 pyenv

```bash
curl https://pyenv.run | bash

cat >> ~/.bashrc << 'EOF'
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
EOF
source ~/.bashrc
pyenv --version
```

---

## 第 4 步：编译安装 Python 3.11.9（约 15～25 分钟）

```bash
export PYTHON_BUILD_MIRROR_URL="https://mirrors.huaweicloud.com/python"
unset PYTHON_CONFIGURE_OPTS
export CPPFLAGS="-I/usr/include/openssl11"
export LDFLAGS="-L/usr/lib64/openssl11 -Wl,-rpath,/usr/lib64/openssl11"
export LD_LIBRARY_PATH="/usr/lib64/openssl11"
export PKG_CONFIG_PATH="/usr/lib64/pkgconfig"

pyenv install 3.11.9
pyenv global 3.11.9
python --version    # 必须显示 Python 3.11.9
which python        # 应在 /root/.pyenv/shims/python
```

成功标志：日志末尾有 `Installed Python-3.11.9`，且存在：

```bash
ls /root/.pyenv/versions/3.11.9/bin/python3
```

若 `BUILD FAILED` 且含 `_ssl`，确认第 2 步 openssl11 已装，并重新执行第 4 步（先 `rm -rf ~/.pyenv/versions/3.11.9`）。

---

## 第 5 步：确认 Node.js

```bash
node --version   # 需要 v16+
which node
```

宝塔常见路径：

```text
/www/server/nvm/versions/node/v16.20.0/bin/node
```

记下路径，后面写入 systemd。

---

## 第 6 步：安装 Python 依赖

```bash
cd /www/wwwroot/Codex

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

pip install -U pip
pip install -r requirements.txt
```

`requirements.txt` 已包含 `requests`；若报缺模块，再 `pip install 模块名`。

---

## 第 7 步：前台试跑（可选）

```bash
cd /www/wwwroot/Codex
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

export ADMIN_PASSWORD='你的强密码'
export NODE_EXECUTABLE=/www/server/nvm/versions/node/v16.20.0/bin/node

python tools/session_converter_web.py --host 0.0.0.0 --port 8766
```

浏览器访问 `http://服务器IP:8766`，正常后 `Ctrl+C` 停掉，进入第 8 步。

---

## 第 8 步：systemd 开机自启（推荐）

```bash
cd /www/wwwroot/Codex
cp deploy/codex-web.service.example /etc/systemd/system/codex-web.service
vi /etc/systemd/system/codex-web.service
```

必改三项：

- `WorkingDirectory` → 你的项目路径  
- `ADMIN_PASSWORD` → 强密码  
- `NODE_EXECUTABLE` → 第 5 步的 `which node` 路径  

```bash
systemctl daemon-reload
systemctl enable codex-web
systemctl start codex-web
systemctl status codex-web
```

日志：

```bash
journalctl -u codex-web -f
tail -f /www/wwwroot/Codex/data/server.log
```

---

## 第 9 步：放行端口

- 云厂商安全组：入站 **8766**  
- 宝塔：安全 → 放行 **8766**  

访问：

- 前台：`http://公网IP:8766`  
- 后台：`http://公网IP:8766/admin`  

---

## 日常维护命令

```bash
systemctl status codex-web      # 是否在跑
systemctl restart codex-web     # 改代码或配置后重启
systemctl stop codex-web        # 停止
journalctl -u codex-web -n 50   # 最近日志
```

---

## 从 GitHub 更新（推荐）

见 **[docs/UPDATE.md](UPDATE.md)**。简要：

```bash
cd /www/wwwroot/Codex
./scripts/update-server.sh
```

**`git pull` 不会删除 `data/card_system.db`。**

后台可在 **版本按钮** 中检查更新、备份数据库；启用 `ENABLE_SELF_UPDATE=1` 后可一键更新。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| `SyntaxError` / `dict[str, float]` | 用了系统 `python 2.7`，必须用 pyenv 的 `python` |
| `_ssl` / `BUILD FAILED` | 重装 openssl11，按第 4 步环境变量重装 |
| `No module named 'requests'` | `pip install requests` |
| 日志 `near "ON": syntax error` | 使用仓库最新 `core/card_store.py`（`INSERT OR REPLACE`） |
| 关 SSH 就停 | 未用 systemd，请完成第 8 步 |
| Sentinel 失败 | 检查 `NODE_EXECUTABLE` 路径 |

---

## 与 Docker 方式对比

| | 本指南（pyenv） | Docker |
|--|----------------|--------|
| 适用 | 已按此方式装好的 CentOS 7 | 新机 / 不想编译 |
| 升级 | `git pull` + `systemctl restart` | `docker compose pull/build` |
| 迁移 | 需在新机重复 pyenv 步骤 | `docker compose up` 即可 |

---

## 一键命令备忘（已装好 pyenv 后）

```bash
cd /www/wwwroot/Codex && \
  export PYENV_ROOT="$HOME/.pyenv" PATH="$PYENV_ROOT/bin:$PATH" && \
  eval "$(pyenv init - bash)" && \
  pip install -r requirements.txt && \
  systemctl restart codex-web && \
  systemctl status codex-web
```
