#!/usr/bin/env bash
# One-shot fix: GitHub version check in Docker (run on server as root)
set -e
cd /www/wwwroot/Codex

cat > core/app_version.py << 'PYEOF'
# -*- coding: utf-8 -*-
"""应用版本与 GitHub 更新检查。"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
DEFAULT_GITHUB_REPO = "Aze0920/Codex_Credential_Manager"


def _parse_version(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", text.strip())
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def get_app_version() -> str:
    if VERSION_FILE.is_file():
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value.splitlines()[0].strip()
    return "0.0.0"


def compare_versions(current: str, remote: str) -> int:
    a = _parse_version(current)
    b = _parse_version(remote)
    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))
    b = b + (0,) * (length - len(b))
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def get_github_repo() -> str:
    return (os.environ.get("GITHUB_REPO") or DEFAULT_GITHUB_REPO).strip().strip("/")


def _fetch_url_text(url: str, *, timeout: int = 12, accept: str | None = None) -> str | None:
    headers = {"User-Agent": "Codex-Credential-Console"}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace").strip()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _fetch_github_json(url: str) -> dict[str, Any] | None:
    body = _fetch_url_text(url, accept="application/vnd.github+json")
    if not body:
        return None
    try:
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _fetch_remote_version_file(repo: str) -> dict[str, Any] | None:
    for branch in ("main", "master"):
        bust = int(time.time())
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/VERSION?_{bust}"
        text = _fetch_url_text(url)
        if not text:
            continue
        tag = text.splitlines()[0].strip().lstrip("vV")
        if tag:
            return {
                "available": True,
                "source": "raw",
                "repo": repo,
                "tag": tag,
                "name": tag,
                "publishedAt": None,
                "htmlUrl": f"https://github.com/{repo}/blob/{branch}/VERSION",
                "body": "",
            }
    return None


def fetch_remote_release() -> dict[str, Any]:
    repo = get_github_repo()
    latest = _fetch_github_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if latest and latest.get("tag_name"):
        tag = str(latest["tag_name"]).lstrip("vV")
        return {
            "available": True,
            "source": "release",
            "repo": repo,
            "tag": tag,
            "name": str(latest.get("name") or tag),
            "publishedAt": latest.get("published_at"),
            "htmlUrl": latest.get("html_url") or f"https://github.com/{repo}/releases/latest",
            "body": str(latest.get("body") or "").strip(),
        }

    tags_body = _fetch_url_text(
        f"https://api.github.com/repos/{repo}/tags",
        accept="application/vnd.github+json",
    )
    if tags_body:
        try:
            tags = json.loads(tags_body)
        except json.JSONDecodeError:
            tags = None
        if isinstance(tags, list) and tags:
            tag = str(tags[0].get("name") or "").lstrip("vV")
            if tag:
                return {
                    "available": True,
                    "source": "tag",
                    "repo": repo,
                    "tag": tag,
                    "name": tag,
                    "publishedAt": None,
                    "htmlUrl": f"https://github.com/{repo}/releases",
                    "body": "",
                }

    raw = _fetch_remote_version_file(repo)
    if raw:
        return raw

    return {
        "available": False,
        "source": "none",
        "repo": repo,
        "tag": None,
        "name": None,
        "publishedAt": None,
        "htmlUrl": f"https://github.com/{repo}",
        "body": "",
        "error": "无法连接 GitHub",
    }


def build_version_payload(*, include_remote: bool = True) -> dict[str, Any]:
    current = get_app_version()
    payload: dict[str, Any] = {
        "version": current,
        "githubRepo": get_github_repo(),
        "selfUpdateEnabled": (os.environ.get("ENABLE_SELF_UPDATE") or "").strip().lower() in {"1", "true", "yes"},
        "updateScript": (os.environ.get("UPDATE_SCRIPT") or str(PROJECT_ROOT / "scripts" / "update-server.sh")).strip(),
    }
    if not include_remote:
        return payload

    remote = fetch_remote_release()
    latest = remote.get("tag")
    payload["remote"] = remote
    if latest:
        cmp = compare_versions(current, str(latest))
        payload["updateAvailable"] = cmp < 0
        payload["upToDate"] = cmp >= 0
    else:
        payload["updateAvailable"] = False
        payload["upToDate"] = None
    return payload
PYEOF

grep -q 'app_version.py:/app/core/app_version.py' docker-compose.yml 2>/dev/null || \
  sed -i '/\.\/VERSION:\/app\/VERSION:ro/a\      - ./core/app_version.py:/app/core/app_version.py:ro' docker-compose.yml

docker compose up -d --force-recreate
sleep 2
echo "=== test ==="
docker exec codex-credential-manager cat /app/VERSION
docker exec codex-credential-manager python3 -c "from core.app_version import fetch_remote_release; r=fetch_remote_release(); print('github', r.get('tag'), r.get('source'))"
echo "=== done, refresh admin version page ==="
