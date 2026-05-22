# -*- coding: utf-8 -*-
"""应用版本与 GitHub 更新检查。"""
from __future__ import annotations

import base64
import json
import os
import re
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


def _version_file_candidates() -> list[Path]:
    """Prefer host project VERSION (git pull) over image /app/VERSION when Docker mounts differ."""
    paths: list[Path] = []
    host_dir = Path(get_host_install_dir())
    host_version = host_dir / "VERSION"
    if host_version.is_file():
        paths.append(host_version)
    if VERSION_FILE.is_file() and VERSION_FILE not in paths:
        paths.append(VERSION_FILE)
    return paths


def get_app_version() -> str:
    for path in _version_file_candidates():
        value = path.read_text(encoding="utf-8").strip()
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


def get_update_script_path() -> str:
    override = (os.environ.get("UPDATE_SCRIPT") or "").strip()
    if override:
        return override
    for candidate in (
        PROJECT_ROOT / "scripts" / "update-docker.sh",
        Path("/host-codex/scripts/update-docker.sh"),
        PROJECT_ROOT / "scripts" / "update-server.sh",
    ):
        if candidate.is_file():
            return str(candidate)
    return str(PROJECT_ROOT / "scripts" / "update-docker.sh")


def get_host_install_dir() -> str:
    for candidate in (
        (os.environ.get("HOST_INSTALL_DIR") or "").strip(),
        "/host-codex",
        str(PROJECT_ROOT),
    ):
        if candidate and Path(candidate).is_dir():
            return candidate
    return str(PROJECT_ROOT)


def check_update_readiness() -> dict[str, Any]:
    issues: list[str] = []
    install_dir = get_host_install_dir()
    script = Path(get_update_script_path())
    if not (os.environ.get("ENABLE_SELF_UPDATE") or "").strip().lower() in {"1", "true", "yes"}:
        issues.append("未设置 ENABLE_SELF_UPDATE=1")
    if not script.is_file():
        issues.append(f"更新脚本不存在: {script}")
    if install_dir == str(PROJECT_ROOT) and not (PROJECT_ROOT / ".git").is_dir():
        issues.append("未挂载宿主机项目目录（需要 .:/host-codex），请重建 Docker 容器")
    if install_dir != str(PROJECT_ROOT) and not (Path(install_dir) / ".git").is_dir():
        issues.append(f"宿主机目录不是 git 仓库: {install_dir}")
    if not Path("/var/run/docker.sock").exists():
        issues.append("未挂载 docker.sock，无法一键重建容器")
    return {
        "ready": len(issues) == 0,
        "issues": issues,
        "installDir": install_dir,
        "updateScript": str(script),
    }


def _fetch_url_text(url: str, *, timeout: int = 12, accept: str | None = None) -> str | None:
    headers = {
        "User-Agent": "Codex-Credential-Console",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    }
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


def _version_tag_from_text(text: str) -> str | None:
    tag = text.splitlines()[0].strip().lstrip("vV") if text else ""
    return tag or None


def _remote_version_payload(repo: str, tag: str, *, source: str, html_url: str) -> dict[str, Any]:
    return {
        "available": True,
        "source": source,
        "repo": repo,
        "tag": tag,
        "name": tag,
        "publishedAt": None,
        "htmlUrl": html_url,
        "body": "",
    }


def _fetch_main_commit_sha(repo: str) -> str | None:
    data = _fetch_github_json(f"https://api.github.com/repos/{repo}/commits/main")
    if data and data.get("sha"):
        return str(data["sha"]).strip()
    return None


def _fetch_remote_version_file(repo: str) -> dict[str, Any] | None:
    """Read main/VERSION only. Never use Release/tags (they lag behind git push)."""
    contents = _fetch_github_json(f"https://api.github.com/repos/{repo}/contents/VERSION?ref=main")
    if contents and contents.get("content"):
        try:
            raw = base64.b64decode(str(contents["content"]).replace("\n", ""))
            tag = _version_tag_from_text(raw.decode("utf-8", errors="replace"))
            if tag:
                return _remote_version_payload(
                    repo,
                    tag,
                    source="api-contents",
                    html_url=str(contents.get("html_url") or f"https://github.com/{repo}/blob/main/VERSION"),
                )
        except (ValueError, OSError):
            pass

    sha = _fetch_main_commit_sha(repo)
    if sha:
        text = _fetch_url_text(
            f"https://raw.githubusercontent.com/{repo}/{sha}/VERSION?sha={sha[:12]}"
        )
        tag = _version_tag_from_text(text or "")
        if tag:
            return _remote_version_payload(
                repo,
                tag,
                source="raw-sha",
                html_url=f"https://github.com/{repo}/blob/main/VERSION",
            )

    for branch in ("main", "master"):
        text = _fetch_url_text(
            f"https://raw.githubusercontent.com/{repo}/{branch}/VERSION?ref={branch}"
        )
        tag = _version_tag_from_text(text or "")
        if tag:
            return _remote_version_payload(
                repo,
                tag,
                source="raw-branch",
                html_url=f"https://github.com/{repo}/blob/{branch}/VERSION",
            )
    return None


def fetch_remote_release() -> dict[str, Any]:
    """Remote version = main/VERSION on GitHub (sync via git push)."""
    repo = get_github_repo()
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
        "htmlUrl": f"https://github.com/{repo}/blob/main/VERSION",
        "body": "",
        "error": "无法读取 GitHub 上 main/VERSION；请确认服务器能访问 api.github.com",
    }


def build_version_payload(*, include_remote: bool = True) -> dict[str, Any]:
    current = get_app_version()
    payload: dict[str, Any] = {
        "version": current,
        "githubRepo": get_github_repo(),
        "selfUpdateEnabled": (os.environ.get("ENABLE_SELF_UPDATE") or "").strip().lower() in {"1", "true", "yes"},
        "updateScript": get_update_script_path(),
        "updateReadiness": check_update_readiness(),
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
