# Codex Credential Console

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**English** | [中文](README.md)

> **GitHub repository description (paste into About)**  
> **EN:** Codex Credential Console — card-key redemption, dual PP/GO account pools, ChatGPT login & multi-format session export (sub2api, CPA, etc.). Docker-ready.  
> **中文：** Codex 凭证管理 — 卡密取号、账号池与 Session 导出，支持 Docker 一键部署。

---

## Overview

**Codex Credential Console** (中文名：**Codex凭证管理**) is a self-hosted web console for Codex / ChatGPT account operations:

- Import Outlook (and other) materials in the admin panel
- Manage **PP / GO** pools and redemption card keys
- Let end users claim accounts via card keys and export sessions locally in the browser
- Export formats compatible with **[sub2api](https://github.com/Wei-Shaw/sub2api)**, CPA, Cockpit, 9router, and AxonHub

This public repository ships **without** real accounts, card keys, or database files.

[Changelog](CHANGELOG.md) · [Acknowledgments](docs/ACKNOWLEDGMENTS.md) · [Screenshots guide](docs/SCREENSHOTS.md) · [中文 README](README.md)

---

## Features

- Card-key generation and one-key-one-account redemption
- Account pool: import, health check, quota, proxy, scheduled auto-test
- Front office: redeem, OTP, session fetch, export
- Admin: stats, logs, API gateway, settings
- Deploy via Docker, Windows, macOS, or Linux scripts

---

## Quick start (Docker)

```bash
git clone https://github.com/Aze0920/Codex_Credential_Manager.git && \
  cd Codex_Credential_Manager && \
  cp .env.example .env && \
  nano .env && \
  docker compose up -d --build
```

Set a strong `ADMIN_PASSWORD` in `.env`.

| Page | URL |
|------|-----|
| Front office | http://127.0.0.1:8766 |
| Admin | http://127.0.0.1:8766/admin |

---

## Local run

| OS | Command |
|----|---------|
| Windows | `run-windows.bat` or `run-windows-en.bat` |
| macOS | `chmod +x run-mac.sh && ./run-mac.sh` |
| Linux | `chmod +x run.sh && ./run.sh` |

Requirements: **Python 3.10+**, **Node.js 16+**.

---

## Environment

| Variable | Description |
|----------|-------------|
| `ADMIN_PASSWORD` | Admin panel password (change in production) |
| `NODE_EXECUTABLE` | Path to `node` binary |
| `HOST` / `PORT` | Bind address and port (default `8766`) |

See [.env.example](.env.example).

---

## Acknowledgments

Session export layout and parts of OAuth / connectivity testing are informed by **[sub2api](https://github.com/Wei-Shaw/sub2api)**. Multi-format conversion ideas reference [GPTSession2CPAandSub2API](https://gtxx3600.github.io/GPTSession2CPAandSub2API/).

See [docs/ACKNOWLEDGMENTS.md](docs/ACKNOWLEDGMENTS.md).

---

## License

[MIT](LICENSE). sub2api itself is licensed under its upstream project terms.

---

## Disclaimer

For learning and self-hosted use only. Comply with upstream ToS and applicable laws. Change default passwords before exposing to the internet.
