# 从 pyenv/systemd 迁到 Docker（保留数据）

适用：已在 `/www/wwwroot/Codex` 用宝塔 + pyenv 跑起来的服务器。

## 会保留什么

| 保留 | 路径 |
|------|------|
| 数据库 | `data/card_system.db` |
| 备份 | `data/backups/` |
| 配置 | 复制为 `.env` |

## 第 1 步：备份（建议）

```bash
cd /www/wwwroot/Codex
cp data/card_system.db data/backups/before-docker-$(date +%Y%m%d).db
```

## 第 2 步：停掉旧服务

```bash
systemctl stop codex-web
systemctl disable codex-web
```

确认 8766 已释放：

```bash
ss -lntp | grep 8766
```

## 第 3 步：安装 Docker（宝塔）

宝塔 → **软件商店** → 安装 **Docker**、**Docker Compose**（或 Compose 插件）。

SSH 验证：

```bash
docker --version
docker compose version
```

CentOS 7 若装不上，可继续用 pyenv 方式，不必强求 Docker。

## 第 4 步：配置 .env

```bash
cd /www/wwwroot/Codex
cp .env.example .env
vi .env
```

至少设置（与原来 systemd 里一致）：

```env
ADMIN_PASSWORD=你的后台密码
HOST=0.0.0.0
PORT=8766
GITHUB_REPO=Aze0920/Codex_Credential_Manager
```

> Docker 版**不要**设 `ENABLE_SELF_UPDATE=1`（一键更新脚本是给 systemd 用的）。  
> 更新用下面「Docker 更新」命令。

## 第 5 步：启动

```bash
cd /www/wwwroot/Codex
docker compose up -d --build
docker ps
docker logs -f codex-credential-manager
```

访问：`http://公网IP:8766` · 后台 `/admin`

## 第 6 步：防火墙

宝塔 / 云安全组放行 **8766**（与之前相同）。

---

## Docker 日常更新

**推荐：管理后台 → 版本与更新 → 一键更新**

Web 容器**不会**自己跑完整更新（`compose up` 会删掉 Web 容器）。流程是：

1. Web API 用 `docker.sock` 拉起一次性容器 **`codex-update-job`**（Alpine）
2. 任务容器在宿主机目录 `/host-codex`（即 `/www/wwwroot/Codex`）里执行 `scripts/update-docker.sh`：`git fetch` → `compose up --build`
3. 进度写在 `data/update-latest.log`；重建期间页面可能短暂 502，等进度到 100% 即可

**SSH 手动更新**（与一键更新同一脚本，需在能访问 docker.sock 的环境执行）：

```bash
cd /www/wwwroot/Codex
docker run --rm --network host \
  -v "$(pwd):/work" -v /var/run/docker.sock:/var/run/docker.sock \
  -v /usr/local/bin/docker-compose:/usr/local/bin/docker-compose:ro \
  -e HOST_INSTALL_DIR=/work -e COMPOSE_PROJECT_NAME=codex \
  alpine:3.20 sh /work/scripts/update-docker.sh
```

或：`git fetch origin main && git reset --hard origin/main` + `docker compose -p codex up -d --build --force-recreate`

数据在 `./data` 挂载卷，**不会丢库**。

---

## 回滚到 pyenv（可选）

```bash
cd /www/wwwroot/Codex
docker compose down
systemctl enable codex-web
systemctl start codex-web
```

---

## 关于后台「GitHub 最新：未知」

这是服务器访问 `api.github.com` / `raw.githubusercontent.com` 的网络问题，**与 pyenv 或 Docker 无关**。

- 版本号以本地 `VERSION` 为准（你已是 v1.0.5）  
- 更新用 `git fetch` + `docker compose up -d --build`  
- 不必依赖后台对比 GitHub
