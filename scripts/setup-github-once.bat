@echo off
title Codex GitHub Setup
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-github-once.ps1"
echo.
pause
