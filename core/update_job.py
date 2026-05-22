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


def start_update_job() -> dict[str, Any]:
    with _lock:
        status = get_update_status()
        if status["running"] or _job_running():
            return {"ok": True, "alreadyRunning": True, **status}

        install_dir = get_host_install_dir()
        script_host = Path(install_dir) / "scripts" / "update-docker.sh"
        if not script_host.is_file():
            script_host = Path("/host-codex/scripts/update-docker.sh")
        if not script_host.is_file():
            return {"ok": False, "error": f"更新脚本不存在: {script_host}"}

        if not Path("/var/run/docker.sock").exists():
            return {"ok": False, "error": "未挂载 docker.sock，无法一键更新"}

        _DATA.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text("[progress] 0|准备启动更新容器…\n", encoding="utf-8")

        docker = _docker_bin()
        env = _docker_env()
        subprocess.run(
            [docker, "rm", "-f", JOB_CONTAINER],
            capture_output=True,
            timeout=30,
            env=env,
        )

        # 包装：任何秒退都写入 data/update-latest.log
        inner = (
            "set -e; "
            "LOG=/work/data/update-latest.log; "
            "mkdir -p /work/data; "
            "echo '[progress] 1|更新容器已启动 (docker:27-cli)' >>\"$LOG\"; "
            "docker version >>\"$LOG\" 2>&1 || true; "
            "apk add --no-cache git curl >>\"$LOG\" 2>&1 || true; "
            "sed -i 's/\\r$//' /work/scripts/update-docker.sh 2>/dev/null || true; "
            "sh /work/scripts/update-docker.sh >>\"$LOG\" 2>&1 "
            "|| { echo \"[error] 更新脚本退出码 $?\" >>\"$LOG\"; exit 1; }"
        )
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
            "-e",
            "HOST_INSTALL_DIR=/work",
            "-e",
            "UPDATE_LOG_FILE=/work/data/update-latest.log",
            "-e",
            "COMPOSE_PROJECT_NAME=codex",
            UPDATE_RUNNER_IMAGE,
            "sh",
            "-c",
            inner,
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            LOG_FILE.write_text(
                LOG_FILE.read_text(encoding="utf-8", errors="replace")
                + f"\n[error] 启动更新容器失败: {exc}\n",
                encoding="utf-8",
            )
            return {"ok": False, "error": f"启动更新容器失败: {exc}", "log": _read_log_tail()}

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            LOG_FILE.write_text(
                LOG_FILE.read_text(encoding="utf-8", errors="replace")
                + f"\n[error] docker run 失败: {err}\n",
                encoding="utf-8",
            )
            return {"ok": False, "error": err or "启动更新容器失败", "log": _read_log_tail()}

        for _ in range(8):
            time.sleep(0.4)
            if _job_running():
                return {
                    "ok": True,
                    "started": True,
                    "message": "更新已在独立容器中运行",
                    "logPath": str(LOG_FILE),
                }

        msg = _failure_message(prefix="更新容器启动后立即退出")
        return {"ok": False, "error": msg, "log": _read_log_tail()}
