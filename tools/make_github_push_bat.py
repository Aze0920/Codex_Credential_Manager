# -*- coding: utf-8 -*-
"""Regenerate push-to-github.bat (ASCII launcher). Setup uses setup-github-once.ps1."""
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

push_bat = """@echo off
title Codex Push to GitHub
cd /d "%~dp0.."
if errorlevel 1 (
    echo [error] Cannot open project folder
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0push-to-github.ps1" %*
if errorlevel 1 (
    echo.
    echo Push failed. See docs\\GITHUB-PUSH.md
    pause
)
exit /b %errorlevel%
"""

setup_bat = """@echo off
title Codex GitHub Setup
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-github-once.ps1"
echo.
pause
"""

for name, content in [("push-to-github.bat", push_bat), ("setup-github-once.bat", setup_bat)]:
    path = SCRIPTS / name
    path.write_bytes(content.replace("\n", "\r\n").encode("ascii"))
    print("written", path)
