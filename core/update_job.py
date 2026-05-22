# -*- coding: utf-8 -*-
"""后台一键更新：独立 Docker 任务容器执行，Web 容器只负责启动与读日志。"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from core.app_version import get_host_install_dir

_DATA = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = _DATA / "update-latest.log"
JOB_CONTAINER = "codex-update-job"
_lock = __import__("threading").Lock()

_PROGRESS_RE = re.compile(r"^\[progress\]\s*(\d+)\|(.*)$")


def _docker_bin() -> str:
    for candidate in ("/usr/local/bin/docker", "/usr/bin/docker", "docker"):
        if candidate != "docker" and Path(candidate).is_file():
            return candidate
    return "docker"


def _compose_bin_host() -> str:
    for candidate in ("/usr/local/bin/docker-compose", "/usr/bin/docker-compose"):
        if Path(candidate).is_file():
            return candidate
    return "/usr/local/bin/docker-compose"


def _update_script_path(install_dir: str) -> Path:
    for candidate in (
        Path(install_dir) / "scripts" / "update-docker.sh",
        Path("/host-codex/scripts/update-docker.sh"),
    ):
        if candidate.is_file():
            return candidate
    return Path(install_dir) / "scripts/update-docker.sh"


def _dedupe_log_lines(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    prev: str | None = None
    for line in lines:
        if line != prev:
            out.append(line)
        prev = line
    return "\n".join(out)


def _read_log_tail(*, max_chars: int = 24000) -> str:
    if not LOG_FILE.is_file():
        return ""
    text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
    text = _dedupe_log_lines(text)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _parse_log_state(text: str) -> dict[str, Any]:
    progress = 0
    message = "等待开始…"
    state = "running"
    error: str | None = None

    for line in text.splitlines():
        match = _PROGRESS_RE.match(line.strip())
        if match:
            progress = max(progress, min(100, int(match.group(1))))
            message = match.group(2).strip() or message
        if "[error]" in line:
            state = "failed"
            error = line.split("[error]", 1)[-1].strip() or error
        if "[done]" in line:
            state = "success"
            progress = 100
            message = "更新完成"

    return {
        "state": state,
        "progress": progress,
        "message": message,
        "error": error,
    }


def _job_running() -> bool:
    try:
        out = subprocess.run(
            [_docker_bin(), "ps", "-q", "-f", f"name=^{JOB_CONTAINER}$"],
            capture_output=True,
            text=True,
            timeout=8,
            env={**os.environ, "DOCKER_HOST": os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")},
        )
        return bool((out.stdout or "").strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def get_update_status() -> dict[str, Any]:
    log = _read_log_tail()
    parsed = _parse_log_state(log)
    running = _job_running()
    if parsed["state"] in {"success", "failed"}:
        running = False
    elif not running and log.strip() and "[done]" not in log and "[error]" not in log:
        parsed["state"] = "failed"
        parsed["error"] = parsed["error"] or "更新任务已结束但未完成，请查看日志"
    return {
        "running": running,
        "log": log,
        "logPath": str(LOG_FILE),
        **parsed,
    }


def start_update_job() -> dict[str, Any]:
    with _lock:
        status = get_update_status()
        if status["running"] or _job_running():
            return {"ok": True, "alreadyRunning": True, **status}

        install_dir = get_host_install_dir()
        script = _update_script_path(install_dir)
        if not script.is_file():
            return {"ok": False, "error": f"更新脚本不存在: {script}"}

        if not Path("/var/run/docker.sock").exists():
            return {"ok": False, "error": "未挂载 docker.sock，无法一键更新"}

        compose_bin = _compose_bin_host()
        _DATA.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text("[progress] 0|准备启动更新容器…\n", encoding="utf-8")

        docker = _docker_bin()
        subprocess.run(
            [docker, "rm", "-f", JOB_CONTAINER],
            capture_output=True,
            timeout=30,
            env={**os.environ, "DOCKER_HOST": "unix:///var/run/docker.sock"},
        )

        script_in_container = "/work/scripts/update-docker.sh"
        cmd = [
            docker,
            "run",
            "-d",
            "--rm",
            "--name",
            JOB_CONTAINER,
            "--network",
            "host",
            "-v",
            f"{install_dir}:/work",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-v",
            f"{compose_bin}:/usr/local/bin/docker-compose:ro",
            "-e",
            "HOST_INSTALL_DIR=/work",
            "-e",
            f"UPDATE_LOG_FILE=/work/data/update-latest.log",
            "-e",
            "COMPOSE_PROJECT_NAME=codex",
            "alpine:3.20",
            "sh",
            script_in_container,
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "DOCKER_HOST": "unix:///var/run/docker.sock"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "error": f"启动更新容器失败: {exc}"}

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            return {"ok": False, "error": err or "启动更新容器失败"}

        time.sleep(0.5)
        if not _job_running():
            return {"ok": False, "error": "更新容器启动后立即退出，请查看 data/update-latest.log"}

        return {
            "ok": True,
            "started": True,
            "message": "更新已在独立容器中运行",
            "logPath": str(LOG_FILE),
        }
