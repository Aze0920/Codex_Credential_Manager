# 更新与备份

## 现有服务器怎么更新（pyenv + systemd）

**正常 `git pull` 不会删除数据库。** 数据在 `data/card_system.db`（或你设置的 `DATABASE_PATH`），不在 Git 仓库里。

### 推荐：命令行更新

```bash
cd /www/wwwroot/Codex
chmod +x scripts/update-server.sh
export INSTALL_DIR=/www/wwwroot/Codex
./scripts/update-server.sh
```

脚本会：`git pull` → `pip install` → **自动备份数据库** → `systemctl restart codex-web`

### 手动更新

```bash
cd /www/wwwroot/Codex
systemctl stop codex-web

cp data/card_system.db data/backups/manual-$(date +%Y%m%d).db   # 建议先备份

git pull
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
pip install -r requirements.txt

systemctl start codex-web
```

### Docker 更新

```bash
cd Codex_Credential_Manager
docker compose exec codex-credential-manager cp /app/data/card_system.db /app/data/backups/pre-update.db 2>/dev/null || true
git pull
docker compose up -d --build
```

`data/` 挂载卷保留，**数据库不会丢**。

---

## 后台「版本 / 更新」按钮

后台顶部 **「刷新统计」左侧** 有 **当前版本号** 按钮：

1. 点击查看：当前版本、GitHub 最新版本、更新说明链接  
2. **检查更新**：对比 GitHub Release/Tag  
3. **备份数据库**：下载或生成 `data/backups/` 备份  
4. **执行更新**（可选）：需在服务器设置 `ENABLE_SELF_UPDATE=1`

### 启用后台一键更新（仅 Linux 服务器）

在 `/etc/systemd/system/codex-web.service` 的 `[Service]` 增加：

```ini
Environment=ENABLE_SELF_UPDATE=1
Environment=GITHUB_REPO=Aze0920/Codex_Credential_Manager
Environment=UPDATE_SCRIPT=/www/wwwroot/Codex/scripts/update-server.sh
```

然后：

```bash
chmod +x /www/wwwroot/Codex/scripts/update-server.sh
systemctl daemon-reload
systemctl restart codex-web
```

> 一键更新会执行 `git pull` 并重启服务，请确保项目目录是 git 仓库且已配置远程。

---

## 数据库会不会丢失？

| 操作 | 数据库 |
|------|--------|
| `git pull` / 覆盖代码 | **不丢**（`data/` 在 .gitignore） |
| `docker compose up --build` | **不丢**（volume 挂载 `./data`） |
| 删除 `data/` 目录 | **会丢** |
| 更新前手动备份 | 可恢复 |

恢复备份：停服务 → 用备份文件覆盖 `data/card_system.db` → 启动服务。

---

## 版本号在哪里？

- 仓库根目录 **`VERSION`** 文件（如 `1.0.4`）
- GitHub 发布 **Release / Tag** 与之对应时，后台会提示有新版本

发布新版本时请：

1. 修改 `VERSION`  
2. 更新 `CHANGELOG.md`  
3. GitHub 创建 Tag / Release（如 `v1.0.4`）
