# 部署方式选择

| 方式 | 文档 | 适合 |
|------|------|------|
| **Docker（推荐新机）** | 下文 | Ubuntu / Debian / CentOS 8+、不想编译 Python |
| **CentOS 7 裸机（你当前方式）** | [DEPLOY-SERVER.md](DEPLOY-SERVER.md) | 已用 pyenv + systemd 的服务器 |

---

## Docker 一键部署

```bash
git clone https://github.com/Aze0920/Codex_Credential_Manager.git
cd Codex_Credential_Manager
cp .env.example .env
vi .env   # 设置 ADMIN_PASSWORD
docker compose up -d --build
```

访问：`http://服务器IP:8766` · 后台 `/admin`

### 更新

```bash
cd Codex_Credential_Manager
git pull
docker compose up -d --build
```

数据在 `./data/` 卷，不丢库。

### 与 pyenv 冲突

同一台机若已跑 `codex-web` systemd（8766），先：

```bash
systemctl stop codex-web
systemctl disable codex-web
```

再启动 Docker。

---

## 国内镜像

- Docker：配置镜像加速  
- pyenv：见 [DEPLOY-SERVER.md](DEPLOY-SERVER.md) 中华为云 `PYTHON_BUILD_MIRROR_URL`
