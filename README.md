# Codex凭证管理

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**中文** | [English](README.en.md)

> **GitHub 仓库简介（可复制到 About）**  
> **中文：** Codex 凭证管理 — 卡密取号、PP/GO 账号池、ChatGPT 登录与 Session 导出（sub2api / CPA 等）。支持 Docker 一键部署。  
> **English:** Codex Credential Console — card-key redemption, dual account pools, ChatGPT login & multi-format session export. Docker-ready.

---

## 简介

**Codex凭证管理**（英文名：**Codex Credential Console**）是一套面向 Codex / ChatGPT 账号运营场景的 Web 控制台：

- 后台导入 Outlook 等素材，管理 **PP / GO** 双池账号与卡密
- 前台用户凭卡密取号，在浏览器本地完成登录与 Session 导出
- 导出格式兼容 **[sub2api](https://github.com/Wei-Shaw/sub2api)**、CPA、Cockpit、9router、AxonHub 等

> 本仓库为开源发行版，**不包含**任何真实账号、卡密或数据库文件。

[更新日志](CHANGELOG.md) · [鸣谢](docs/ACKNOWLEDGMENTS.md) · [截图规范](docs/SCREENSHOTS.md) · [English README](README.en.md)

---

## 功能概览

| 模块 | 说明 |
|------|------|
| 卡密系统 | 批量生成 `Codex-P` / `Codex-G` 卡密，一卡一号 |
| 账号池 | 导入、测试、额度查询、代理、定时自动检测 |
| 前台 | 卡密取号、OTP、Session 拉取、多格式导出 |
| 后台 | 统计、日志、API 网关、系统设置 |
| 部署 | Docker Compose、Windows / macOS / Linux 本地脚本 |

---

## 预览

> 按 [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md) 将截图放入 `docs/images/` 后，取消下方注释。

<!--
| Codex凭证管理 · 前台 | Codex凭证管理 · 后台 |
|:---:|:---:|
| ![前台](docs/images/01-home.png) | ![后台](docs/images/03-admin-dashboard.png) |
-->

---

## 部署方式

| 场景 | 文档 |
|------|------|
| **云服务器 CentOS 7（pyenv + systemd）** | [docs/DEPLOY-SERVER.md](docs/DEPLOY-SERVER.md) · [docs/UPDATE.md](docs/UPDATE.md) |
| **新机 / Docker 一键** | 下文 + [docs/DEPLOY.md](docs/DEPLOY.md) |

---

## 快速开始（Docker，推荐新机）

**环境：** [Docker](https://docs.docker.com/get-docker/) + Compose

```bash
git clone https://github.com/Aze0920/Codex_Credential_Manager.git && \
  cd Codex_Credential_Manager && \
  cp .env.example .env && \
  nano .env && \
  docker compose up -d --build
```

在 `.env` 中设置 `ADMIN_PASSWORD`（勿使用示例密码）。

| 页面 | 地址 |
|------|------|
| 前台（Codex凭证管理） | http://127.0.0.1:8766 |
| 后台 | http://127.0.0.1:8766/admin |

```bash
docker compose logs -f
docker compose restart
docker compose down
```

数据保存在宿主机 `./data/`（已在 `.gitignore` 中排除）。

---

## 本地部署

需要 **Python 3.10+**、**Node.js 16+**。

### Windows

1. 安装 [Python 3.11](https://www.python.org/downloads/)（勾选 Add to PATH）
2. 安装 [Node.js 18 LTS](https://nodejs.org/)
3. 运行：

```bat
run-windows.bat
```

乱码或 `'xxx' 不是内部或外部命令` 时，改用 `run-windows-en.bat` 或执行 `python tools\make_run_windows_bat.py` 重新生成中文脚本。

服务管理：`tools\restart_admin.bat`

### macOS

```bash
brew install python@3.11 node@18
chmod +x run-mac.sh && ./run-mac.sh
```

### Linux

```bash
chmod +x run.sh && ./run.sh
```

服务器（CentOS 7 裸机）见 **[docs/DEPLOY-SERVER.md](docs/DEPLOY-SERVER.md)**。

---

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `ADMIN_PASSWORD` | 后台登录密码 | `admin123`（**生产必改**） |
| `NODE_EXECUTABLE` | Node 路径 | 自动探测 |
| `HOST` / `PORT` | 监听地址与端口 | `0.0.0.0` / `8766` |

详见 [.env.example](.env.example)。

---

## 卡密与导出

1. 后台导入 `email----password----clientId----refreshToken`
2. 生成 PP / GO 卡密
3. 前台输入卡密取号 → 登录 → 导出 Session

| 格式 | 说明 |
|------|------|
| **sub2api** | 单文件 `sub2api.json`（兼容 [sub2api](https://github.com/Wei-Shaw/sub2api)） |
| **cpa** | 每邮箱一个 JSON，ZIP |
| 其它 | cockpit / 9router / axonhub |

---

## 目录结构

```text
├── core/                    # 核心业务
├── tools/                   # Web 入口、脚本
├── sentinel/                # Node Sentinel
├── docs/                    # 文档与截图
├── Dockerfile
├── docker-compose.yml
├── install.sh
├── run-windows.bat
├── run-mac.sh
├── README.md                # 中文（本文件）
└── README.en.md             # English
```

---

## 鸣谢

导出格式与部分 OAuth / 账号测试逻辑参考 **[sub2api](https://github.com/Wei-Shaw/sub2api)**；多格式转换思路参考 [GPTSession2CPAandSub2API](https://gtxx3600.github.io/GPTSession2CPAandSub2API/)。

详见 [docs/ACKNOWLEDGMENTS.md](docs/ACKNOWLEDGMENTS.md)。

---

## 上传到 GitHub

**Windows 一键推送：** 阅读 [docs/GITHUB-PUSH.md](docs/GITHUB-PUSH.md)，双击 `scripts/push-to-github.bat`。

## 上传 GitHub 前检查

- [ ] 未提交 `data/*.db`、`data/*.log`、`.env`
- [ ] 确认未包含个人密码或真实账号数据
- [ ] 已阅读 [CHANGELOG.md](CHANGELOG.md)

---

## 许可证

本仓库根目录包含 **[LICENSE](LICENSE)** 文件，采用 **MIT License**（开源协议）。

- 可自由使用、修改、分发本仓库**源码**
- 需保留版权声明与 MIT 协议全文
- 软件按「原样」提供，不提供担保

使用 [sub2api](https://github.com/Wei-Shaw/sub2api) **软件**或向其导入的 JSON 时，请另行遵守 sub2api 原项目的许可与条款（与本仓库 MIT 相互独立）。

推送至 GitHub 后，在仓库主页 **About → License** 会显示 **MIT**（因存在 `LICENSE` 文件）。

---

## 免责声明

仅供学习与研究。请遵守相关服务条款与当地法律。公开部署请务必修改默认密码并限制访问。
