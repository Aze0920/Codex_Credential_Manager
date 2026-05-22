# 更新日志 / Changelog

[中文 README](README.md) · [English README](README.en.md)

## [1.0.27] - 2026-05-22

### 修复

- 一键更新：镜像内安装 **docker CLI**；重建任务改用 alpine + 挂载 docker/compose，修复 `docker: command not found`。
- 更新日志不再重复写入两行。

## [1.0.25] - 2026-05-22

### 新增

- 账号池支持**备注**：导入时可填统一备注（不填为空）；展开账号后双击备注可修改并保存。

## [1.0.24] - 2026-05-22

### 修复

- 容器启动改为 `sh docker-entrypoint.sh`，避免挂载脚本无执行位导致 `permission denied`。
- 取消 `./scripts` 覆盖 `/app/scripts`，更新脚本仍从 `/host-codex/scripts` 读取。

## [1.0.23] - 2026-05-22

### 修复

- 一键更新：重建前强制 `docker rm -f codex-credential-manager` + `compose down`，固定项目名 `codex`，避免容器名冲突。
- 更新脚本优先使用宿主机 `/host-codex/scripts/update-docker.sh`；挂载 `./scripts` 到容器。

## [1.0.22] - 2026-05-22

### 修复

- **版本自动对齐**：容器启动时同步宿主机 VERSION；API 每次读版本前对齐；一键更新强制 `--force-recreate`。宿主机 / 界面 / GitHub 保持一致，无需再手动对版本。

## [1.0.21] - 2026-05-22

### 修复

- 「当前版本」优先读宿主机 `/host-codex/VERSION`（与 `git pull` 一致），避免未重建容器时仍显示镜像内旧版本号。

## [1.0.20] - 2026-05-22

### 修复

- 服务器 `git fetch origin main` 后须 `reset --hard FETCH_HEAD`（不能只用 `origin/main`，否则会卡在旧提交如 1.0.18）。

## [1.0.19] - 2026-05-22

### 修复

- 一键更新：改为后台任务 + 进度条 + 详细日志轮询；用独立 `codex-update-job` 容器执行 compose，避免重建时断开请求误报「操作失败」。

## [1.0.18] - 2026-05-22

### 修复

- 版本检测：只认 GitHub **main/VERSION**（优先 API，不用 Release/标签）；修复 raw CDN 返回旧 1.0.16 导致误报「已是最新」。

## [1.0.17] - 2026-05-22

### 变更

- 后台「关于」页新增「版本与更新」区块：显示当前版本与近期改动说明。

## [1.0.16] - 2026-05-22

### 变更

- 版本弹窗 UI 精简（1.0.15 已改本地；需上传并重启容器后生效）。

## [1.0.15] - 2026-05-22

### 变更

- 版本弹窗：去掉左上角图标、副标题说明和数据库路径行，界面更简洁。

## [1.0.14] - 2026-05-22

### 修复

- GitHub「最新版本」改为取 **main/VERSION、Release、标签** 三者中的最高版本；避免旧 Release（如 v1.0.11）盖住 main 上已推到 1.0.13 的 VERSION。
- `docker-compose.yml` 挂载整个 `core/`、`tools/`，宿主机 `git pull` 后重启容器即可生效，不必每次重建镜像。

## [1.0.9] - 2026-05-22

### 修复

- 一键更新失败时返回明确原因（git / docker.sock / host-codex 挂载）。
- 版本弹窗显示环境未就绪提示。

## [1.0.8] - 2026-05-22

### 变更

- 版本弹窗：毛玻璃与内容分层，弹窗不再被挡住。
- 一键更新：有新版本才可点，点击直接更新（无确认弹窗）；已是最新则按钮禁用。
- Docker 后台一键更新（git + 重建容器），无需 SSH 日常操作。
- GitHub 版本检测改用提交 SHA，避免 raw CDN 缓存。

## [1.7] - 2026-05-22

### 说明

- 测试 GitHub 版本检测与 Docker 更新脚本 `update-docker.sh`。

## [1.0.6] - 2026-05-22

### 修复

- Docker 挂载 `VERSION` / `app_version.py`，GitHub 版本对比（raw 备用）。
- 新增 `scripts/server-fix-version.sh` 服务器一键修复脚本。

## [1.0.5] - 2026-05-22

### 新增

- 补全 `scripts/update-server.sh`（`git fetch` + 备份数据库 + 重启服务）。
- Windows 桌面 `scripts` 一键上传 / 保存 Token 工具。

### 修复

- 服务器旧版 Git 可用 `git reset --hard FETCH_HEAD` 更新。
- 后台版本检查与 `ENABLE_SELF_UPDATE` 说明完善。

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
