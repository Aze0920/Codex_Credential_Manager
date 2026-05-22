#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键更新启动器（独立进程，每次执行加载最新代码，不依赖 Web 进程缓存）。"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ENGINE_VERSION = "1.0.35"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.app_version import get_docker_bind_path  # noqa: E402

LOG_FILE = ROOT / "data" / "update-latest.log"
JOB_CONTAINER = "codex-update-job"
DOCKER = "/usr/local/bin/docker" if Path("/usr/local/bin/docker").is_file() else "docker"


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(msg.rstrip() + "\n")


def _docker_env() -> dict[str, str]:
    return {**os.environ, "DOCKER_HOST": os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")}


def _runner_image() -> str:
    override = (os.environ.get("UPDATE_RUNNER_IMAGE") or "").strip()
    if override:
        return override
    try:
        out = subprocess.run(
            [DOCKER, "inspect", "-f", "{{.Config.Image}}", "codex-credential-manager"],
            capture_output=True,
            text=True,
            timeout=15,
            env=_docker_env(),
        )
        image = (out.stdout or "").strip()
        if image and out.returncode == 0:
            return image
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "docker:27-cli"


def main() -> int:
    bind = get_docker_bind_path()
    LOG_FILE.write_text(
        f"[progress] 0|准备启动更新…\n"
        f"[engine] {ENGINE_VERSION}\n"
        f"[bind] host={bind}\n",
        encoding="utf-8",
    )

    if not bind or bind in {"/host-codex", "/app"}:
        _log("[error] 未配置宿主机路径，请在 .env 设置 HOST_BIND_PATH=/www/wwwroot/Codex 后执行 docker compose up -d --force-recreate")
        return 1

    if not Path("/var/run/docker.sock").exists():
        _log("[error] 未挂载 docker.sock")
        return 1

    env = _docker_env()
    _log(f"[runner] image={_runner_image()}")

    pre = subprocess.run(
        [
            DOCKER,
            "run",
            "--rm",
            "-v",
            f"{bind}:/work:ro",
            "alpine:3.20",
            "sh",
            "-c",
            "test -f /work/docker-compose.yml && test -d /work/.git",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if pre.returncode != 0:
        err = (pre.stderr or pre.stdout or "挂载预检失败").strip()
        _log(f"[error] 预检失败 bind={bind}：{err}")
        return 1

    subprocess.run([DOCKER, "rm", "-f", JOB_CONTAINER], capture_output=True, timeout=30, env=env)

    inner = (
        "set -e; "
        "LOG=/work/data/update-latest.log; "
        "mkdir -p /work/data; "
        "echo '[progress] 1|更新任务容器已启动' >>\"$LOG\"; "
        "docker version >>\"$LOG\" 2>&1 || true; "
        "(command -v git >/dev/null || apk add --no-cache git) >>\"$LOG\" 2>&1 || true; "
        "(command -v curl >/dev/null || apk add --no-cache curl) >>\"$LOG\" 2>&1 || true; "
        "sed -i 's/\\r$//' /work/scripts/update-docker.sh 2>/dev/null || true; "
        "sh /work/scripts/update-docker.sh >>\"$LOG\" 2>&1 "
        "|| { echo \"[error] 更新脚本退出 $?\" >>\"$LOG\"; exit 1; }"
    )

    proc = subprocess.run(
        [
            DOCKER,
            "run",
            "-d",
            "--rm",
            "--name",
            JOB_CONTAINER,
            "--network",
            "host",
            "-v",
            f"{bind}:/work",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-e",
            "HOST_INSTALL_DIR=/work",
            "-e",
            "UPDATE_LOG_FILE=/work/data/update-latest.log",
            "-e",
            "COMPOSE_PROJECT_NAME=codex",
            _runner_image(),
            "sh",
            "-c",
            inner,
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "docker run 失败").strip()
        _log(f"[error] 启动更新容器失败: {err}")
        return 1

    for _ in range(10):
        time.sleep(0.5)
        ps = subprocess.run(
            [DOCKER, "ps", "-q", "-f", f"name=^{JOB_CONTAINER}$"],
            capture_output=True,
            text=True,
            timeout=8,
            env=env,
        )
        if (ps.stdout or "").strip():
            _log("[progress] 3|更新容器运行中")
            return 0

    _log("[error] 更新容器启动后立即退出，请查看上方 [bind] 与 docker 输出")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
