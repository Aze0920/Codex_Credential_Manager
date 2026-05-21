# -*- coding: utf-8 -*-
"""应用版本与 GitHub 更新检查。"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from functools import lru_cache
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
    """Return -1 if current < remote, 0 if equal, 1 if current > remote."""
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


@lru_cache(maxsize=8)
def _fetch_github_json(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Codex-Credential-Console",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
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

    tags = _fetch_github_json(f"https://api.github.com/repos/{repo}/tags")
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

    return {
        "available": False,
        "source": "none",
        "repo": repo,
        "tag": None,
        "name": None,
        "publishedAt": None,
        "htmlUrl": f"https://github.com/{repo}",
        "body": "",
        "error": "无法连接 GitHub 或仓库尚无 Release/Tag",
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
