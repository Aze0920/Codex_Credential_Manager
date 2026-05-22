# -*- coding: utf-8 -*-
"""后台一键更新：独立 Docker 任务容器执行，Web 容器只负责启动与读日志。"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from core.app_version import get_docker_bind_path, get_host_install_dir

_DATA = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = _DATA / "update-latest.log"
JOB_CONTAINER = "codex-update-job"
# 自带 docker compose 插件，不依赖宿主机 /usr/local/bin/docker-compose
UPDATE_RUNNER_IMAGE = (os.environ.get("UPDATE_RUNNER_IMAGE") or "docker:27-cli").strip()
_lock = __import__("threading").Lock()

_PROGRESS_RE = re.compile(r"^\[progress\]\s*(\d+)\|(.*)$")
_ERROR_RE = re.compile(r"^\[error\]\s*(.+)$", re.MULTILINE)


def _docker_bin() -> str:
    for candidate in ("/usr/local/bin/docker", "/usr/bin/docker", "docker"):
        if candidate != "docker" and Path(candidate).is_file():
            return candidate
    return "docker"


def _docker_env() -> dict[str, str]:
    return {**os.environ, "DOCKER_HOST": os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")}


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

    if state == "running" and error is None:
        err_match = _ERROR_RE.search(text)
        if err_match:
            state = "failed"
            error = err_match.group(1).strip()

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
            env=_docker_env(),
        )
        return bool((out.stdout or "").strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def _fetch_container_logs() -> str:
    try:
        out = subprocess.run(
            [_docker_bin(), "logs", "--tail", "80", JOB_CONTAINER],
            capture_output=True,
            text=True,
            timeout=15,
            env=_docker_env(),
        )
        return (out.stdout or out.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _failure_message(*, prefix: str) -> str:
    log = _read_log_tail()
    if log.strip():
        for line in reversed(log.splitlines()):
            if "[error]" in line:
                return f"{prefix}：{line.split('[error]', 1)[-1].strip()}"
            if line.strip() and not line.startswith("[progress] 0|"):
                return f"{prefix}（详见下方日志）"
    docker_logs = _fetch_container_logs()
    if docker_logs:
        last = docker_logs.splitlines()[-1][:200]
        return f"{prefix}：{last}"
    return prefix


def get_update_status() -> dict[str, Any]:
    log = _read_log_tail()
    parsed = _parse_log_state(log)
    running = _job_running()
    if parsed["state"] in {"success", "failed"}:
        running = False
    elif not running and log.strip() and "[done]" not in log and "[error]" not in log:
        parsed["state"] = "failed"
        parsed["error"] = parsed["error"] or _failure_message(prefix="更新任务已结束但未完成")
    return {
        "running": running,
        "log": log,
        "logPath": str(LOG_FILE),
        **parsed,
    }


def _trigger_script_path() -> Path:
    for candidate in (
        Path("/host-codex/scripts/trigger-update.py"),
        Path(__file__).resolve().parent.parent / "scripts" / "trigger-update.py",
    ):
        if candidate.is_file():
            return candidate
    return Path("/host-codex/scripts/trigger-update.py")


def start_update_job() -> dict[str, Any]:
    with _lock:
        status = get_update_status()
        if status["running"] or _job_running():
            return {"ok": True, "alreadyRunning": True, **status}

        bind_path = get_docker_bind_path()
        if bind_path in {"/host-codex", "/app", ""}:
            return {
                "ok": False,
                "error": "请在 .env 设置 HOST_BIND_PATH=/www/wwwroot/Codex 后执行 docker compose -p codex up -d --force-recreate",
                "log": "",
            }

        if not Path("/var/run/docker.sock").exists():
            return {"ok": False, "error": "未挂载 docker.sock，无法一键更新"}

        script = _trigger_script_path()
        if not script.is_file():
            return {"ok": False, "error": f"缺少启动脚本: {script}"}

        _DATA.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text("[progress] 0|正在启动更新进程…\n", encoding="utf-8")

        try:
            proc = subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(script.parent.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except OSError as exc:
            _append_log(f"[error] 无法启动 trigger-update.py: {exc}")
            return {"ok": False, "error": str(exc), "log": _read_log_tail()}

        time.sleep(1.2)
        if proc.poll() is not None and proc.returncode not in (None, 0):
            return {
                "ok": False,
                "error": _failure_message(prefix="更新启动失败"),
                "log": _read_log_tail(),
            }

        if _job_running():
            return {
                "ok": True,
                "started": True,
                "message": "更新已在独立容器中运行",
                "logPath": str(LOG_FILE),
            }

        log = _read_log_tail()
        if "[engine]" in log and "[error]" in log:
            return {"ok": False, "error": _failure_message(prefix="更新启动失败"), "log": log}

        return {
            "ok": True,
            "started": True,
            "message": "更新进程已启动",
            "logPath": str(LOG_FILE),
        }


def _append_log(line: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip() + "\n")
