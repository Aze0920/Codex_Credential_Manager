# 截图规范（维护者 / 贡献者）

适用于 **Codex凭证管理 / Codex Credential Console** 公开 README。

请按本文档拍摄并提交到 `docs/images/`。**切勿**在截图中出现真实邮箱、密码、卡密、Token 或服务器 IP。

## 需要哪些截图

| 文件名 | 内容 | 建议说明 |
|--------|------|----------|
| `01-home.png` | 前台首页（卡密输入框、取号区域） | 卡密用假数据，如 `Codex-P00000000000000000000` |
| `02-admin-login.png` | 后台登录页 | 密码框可留空或打码 |
| `03-admin-dashboard.png` | 后台总览 / 统计 | 无真实账号数据 |
| `04-admin-cards.png` | 卡密管理列表 | 卡密可打码 |
| `05-admin-accounts.png` | 账号池列表 | 邮箱用 `demo@example.com` |
| `06-export.png` | 导出格式选择或下载成功提示 | 可选 |

至少提供 **01、02、03** 三张即可发布首版 README。

## 怎么截图（分系统）

### Windows

1. 本地启动服务：双击 `run-windows.bat`，或先 `tools\restart_admin.bat` 选启动。
2. 浏览器打开 `http://127.0.0.1:8766` 与 `http://127.0.0.1:8766/admin`。
3. 截图方式（任选）：
   - **Win + Shift + S**：区域截图，保存到 `docs/images/`。
   - **浏览器全页**：Edge / Chrome 开发者工具 `F12` → `Ctrl+Shift+P` → 输入 `screenshot` → 选 **Capture full size screenshot**。
4. 建议窗口宽度 **1280px**（浏览器开发者工具 → 切换设备工具栏 → Responsive 1280×720）。

### macOS

1. 终端执行：`chmod +x run-mac.sh && ./run-mac.sh`
2. 打开 `http://127.0.0.1:8766` 与 `/admin`。
3. 截图方式：
   - **Cmd + Shift + 4**，拖选区域，文件在桌面，再移到 `docs/images/`。
   - **Cmd + Shift + 5**：选“截取所选窗口”。
4. 同样建议宽度约 **1280px**。

### Linux

1. `docker compose up -d` 或 `./run.sh` 启动。
2. 使用系统截图工具，或浏览器全页截图（同 Windows Chrome 步骤）。

## 图片要求

- 格式：**PNG**（优先）或 JPEG。
- 宽度：建议 **1200～1400px**，README 中显示清晰。
- 文件大小：单张尽量 **&lt; 500KB**（可用 [TinyPNG](https://tinypng.com/) 压缩）。
- 语言：界面为中文即可，与目标用户一致。

## 提交到 GitHub 前检查

- [ ] 无真实 `email----password----clientId----refreshToken` 素材
- [ ] 无真实卡密、Access Token、Session JSON
- [ ] 无个人服务器公网 IP（演示可用 `127.0.0.1`）
- [ ] 无 `.env` 或密码明文

## 在 README 中引用

将图片放入 `docs/images/` 后，在 `README.md` 的「预览」章节使用：

```markdown
| 前台取号 | 后台管理 |
|:---:|:---:|
| ![前台取号](docs/images/01-home.png) | ![后台管理](docs/images/03-admin-dashboard.png) |
```

## 把截图发给维护者（若你不会 Git）

1. 按上表文件名保存 PNG。
2. 打包为 zip，或发到 Issue / 私信。
3. 说明对应页面是否已打码。

维护者放入 `docs/images/` 后执行：

```bash
git add docs/images/
git commit -m "docs: add README screenshots"
git push
```
