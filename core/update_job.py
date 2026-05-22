# -*- coding: utf-8 -*-
"""后台一键更新任务：日志写入 data/update-latest.log，供轮询进度。"""
from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from core.app_version import get_host_install_dir, get_update_script_path

_DATA = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = _DATA / "update-latest.log"
PID_FILE = _DATA / "update-job.pid"
_lock = threading.Lock()
_proc: subprocess.Popen[str] | None = None

_PROGRESS_RE = re.compile(r"^\[progress\]\s*(\d+)\|(.*)$")


def _ensure_data_dir() -> None:
    _DATA.mkdir(parents=True, exist_ok=True)


def _read_log_tail(*, max_chars: int = 24000) -> str:
    if not LOG_FILE.is_file():
        return ""
    text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
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

    if state == "running" and progress >= 58 and "重建" in message:
        progress = max(progress, 58)

    return {
        "state": state,
        "progress": progress,
        "message": message,
        "error": error,
    }


def _proc_running() -> bool:
    global _proc
    if _proc is not None and _proc.poll() is None:
        return True
    if PID_FILE.is_file():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    return False


def _docker_bin() -> str:
    for candidate in ("/usr/local/bin/docker", "/usr/bin/docker", "docker"):
        if candidate != "docker" and not Path(candidate).is_file():
            continue
        return candidate
    return "docker"


def _sidecar_running() -> bool:
    try:
        out = subprocess.run(
            [_docker_bin(), "ps", "-q", "-f", "name=^codex-update-job$"],
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
    if parsed["state"] in {"success", "failed"}:
        running = False
    else:
        running = _proc_running() or _sidecar_running()
        if not running and log.strip() and parsed["progress"] > 0:
            parsed["state"] = "failed"
            parsed["error"] = parsed["error"] or "更新进程已结束但未完成，请查看下方日志"
            running = False
    return {
        "running": running,
        "log": log,
        "logPath": str(LOG_FILE),
        **parsed,
    }


def start_update_job() -> dict[str, Any]:
    global _proc
    with _lock:
        status = get_update_status()
        if status["running"] or _proc_running():
            return {"ok": True, "alreadyRunning": True, **status}

        script = Path(get_update_script_path())
        if not script.is_file():
            return {"ok": False, "error": f"更新脚本不存在: {script}"}

        install_dir = get_host_install_dir()
        _ensure_data_dir()
        LOG_FILE.write_text("[progress] 0|准备更新…\n", encoding="utf-8")
        PID_FILE.unlink(missing_ok=True)

        log_fp = open(LOG_FILE, "a", encoding="utf-8")

        def _reap() -> None:
            global _proc
            proc = _proc
            if proc is None:
                return
            proc.wait()
            _proc = None
            PID_FILE.unlink(missing_ok=True)
            try:
                log_fp.close()
            except OSError:
                pass

        _proc = subprocess.Popen(
            ["bash", str(script)],
            cwd=install_dir,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            text=True,
            env={
                **__import__("os").environ,
                "INSTALL_DIR": install_dir,
                "HOST_INSTALL_DIR": install_dir,
                "UPDATE_LOG_FILE": str(LOG_FILE),
            },
        )
        PID_FILE.write_text(str(_proc.pid), encoding="utf-8")
        threading.Thread(target=_reap, daemon=True).start()

        return {
            "ok": True,
            "started": True,
            "pid": _proc.pid,
            "logPath": str(LOG_FILE),
            "message": "更新任务已启动",
        }
