# 更新日志 / Changelog

[中文 README](README.md) · [English README](README.en.md)

## [1.0.4] - 2026-05-21

### 新增

- 根目录 `VERSION` 与后台 **版本 / 更新** 按钮（刷新统计左侧）。
- GitHub Release/Tag 对比、数据库备份/下载、可选一键更新（`ENABLE_SELF_UPDATE=1`）。
- `scripts/update-server.sh`：服务器 `git pull` + 备份 + 重启 systemd。
- 文档：[docs/UPDATE.md](docs/UPDATE.md)、[docs/DATABASE.md](docs/DATABASE.md)。
- 环境变量 `DATABASE_PATH` / `SQLITE_PATH` 自定义 SQLite 路径。

### 说明

- **MySQL 安装时输入账号密码**：当前版本尚未支持，见 [docs/DATABASE.md](docs/DATABASE.md)；可用备份恢复代替。

## [1.0.3] - 2026-05-21

### 文档

- 新增 [docs/DEPLOY-SERVER.md](docs/DEPLOY-SERVER.md)：CentOS 7 + pyenv + systemd 分步部署（与早期服务器安装一致）。
- 新增 [deploy/codex-web.service.example](deploy/codex-web.service.example) systemd 模板。

## [1.0.2] - 2026-05-21

### 变更

- 项目对外名称统一为 **Codex凭证管理** / **Codex Credential Console**。
- 新增 [README.en.md](README.en.md)；[README.md](README.md) 顶部提供 GitHub About 中英简介可复制文案。
- 前台 / 后台页面标题与关于文案同步更新。

## [1.0.1] - 2026-05-21

### 修复

- Windows：`run-windows.bat` 改为 GBK 编码，避免 cmd 乱码。
- 新增 `run-windows-en.bat` 与 `tools/make_run_windows_bat.py`。

## [1.0.0] - 2026-05-21

### 新增

- 首次公开发布：卡密取号、账号池、Session 多格式导出。
- Docker / Compose、`install.sh`、Windows / macOS 本地脚本。
- 文档：鸣谢、截图规范、部署说明。
