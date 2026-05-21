# 数据库说明

## 当前实现：SQLite（默认）

- 单文件：`data/card_system.db`
- 含：卡密、账号池、设置、运行日志等
- **无需**安装 MySQL，开箱即用

### 自定义 SQLite 路径

环境变量（二选一）：

```bash
export DATABASE_PATH=/var/lib/codex/card_system.db
# 或
export SQLITE_PATH=/var/lib/codex/card_system.db
```

Docker 在 `.env` 中设置，并挂载对应目录。

---

## 备份与恢复

### 后台

顶部 **版本** 按钮 → **备份数据库**（下载或写入 `data/backups/`）

### 命令行

```bash
cp /www/wwwroot/Codex/data/card_system.db \
   /www/wwwroot/Codex/data/backups/manual-$(date +%Y%m%d).db
```

### 恢复

```bash
systemctl stop codex-web
cp /path/to/backup.db /www/wwwroot/Codex/data/card_system.db
systemctl start codex-web
```

---

## MySQL / PostgreSQL？

**当前版本尚未支持**外置 MySQL 连接（安装时输入账号密码）。

原因：全项目约 2300+ 行直接使用 `sqlite3`，改为 MySQL 需要：

- 统一数据库抽象层  
- 重写 SQL 方言差异  
- 安装迁移工具  

已在路线图中，若你需要可单独开 Issue 排期。

### 现在如何「像 MySQL 一样」防丢数据？

1. 更新前用后台或脚本 **备份 `.db` 文件**  
2. 把 `data/backups/` 同步到对象存储 / 另一台机器  
3. 使用 `DATABASE_PATH` 把库放在独立磁盘或挂载卷  

---

## 安装时配置数据库？

| 方式 | 支持 |
|------|------|
| 默认 SQLite | 是 |
| 环境变量改 SQLite 路径 | 是 |
| 安装向导输入 MySQL 账号密码 | **暂未**（见上） |

Docker：复制 `.env.example`，主要配置 `ADMIN_PASSWORD`；数据在 `./data` 卷。

裸机：见 [DEPLOY-SERVER.md](DEPLOY-SERVER.md)，无需单独装数据库服务。
