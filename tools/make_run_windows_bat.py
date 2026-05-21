# -*- coding: utf-8 -*-
"""Generate run-windows.bat in GBK for Chinese Windows CMD (avoid UTF-8 parse errors)."""
from pathlib import Path

bat = r"""@echo off
title Codex Credential Manager
cd /d "%~dp0"

set "PYCMD=python"
where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if not errorlevel 1 set "PYCMD=py -3"
)
%PYCMD% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] 需要 Python 3.10 或更高版本
    %PYCMD% --version 2>nul
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 node，Sentinel 可能不可用
    echo 安装 Node 16+: https://nodejs.org/
)

if not exist ".venv\Scripts\activate.bat" (
    echo [提示] 创建虚拟环境 .venv ...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建 venv 失败
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络
    pause
    exit /b 1
)

if not exist "data" mkdir "data"

if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

echo.
echo 前台: http://127.0.0.1:8766
echo 后台: http://127.0.0.1:8766/admin
echo 密码: 环境变量 ADMIN_PASSWORD 或默认 admin123
echo 结束: 关闭本窗口，或运行 tools\restart_admin.bat
echo.

python tools\session_converter_web.py --host 127.0.0.1 --port 8766
pause
"""

out = Path(__file__).resolve().parent.parent / "run-windows.bat"
out.write_text(bat, encoding="gbk")
print("written", out)
