# -*- coding: utf-8 -*-
"""Generate restart_admin.bat in GBK for Chinese Windows CMD."""
from pathlib import Path

bat = r"""@echo off
chcp 936 >nul
title Codex Credential Manager
setlocal EnableDelayedExpansion
set "PORT=8766"
set "ROOT=%~dp0.."
cd /d "%ROOT%"
if not exist "data" mkdir "data"

call :CHECK_RUNNING
if "!RUNNING!"=="0" goto AUTO_START

:MENU
cls
echo.
echo ========================================
echo  Codex凭证管理 服务管理
echo ========================================
echo 当前状态: 运行中
echo 访问地址: http://127.0.0.1:!PORT!/
echo 后台地址: http://127.0.0.1:!PORT!/admin
echo.
echo  [1] 重启服务
echo  [2] 结束服务
echo.
set "CHOICE="
set /p "CHOICE=请输入 1 或 2: "
if "!CHOICE!"=="1" goto DO_RESTART
if "!CHOICE!"=="2" goto DO_STOP
echo [警告] 请输入 1 或 2
timeout /t 1 /nobreak >nul
goto MENU

:AUTO_START
echo [提示] 服务未运行, 正在自动启动...
call :START_SERVER
pause
exit /b 0

:DO_STOP
call :KILL_SERVER
echo [成功] 服务已结束
pause
exit /b 0

:DO_RESTART
call :KILL_SERVER
timeout /t 1 /nobreak >nul
call :START_SERVER
pause
goto MENU

:CHECK_RUNNING
set "RUNNING=0"
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do set "RUNNING=1"
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr /i "PID:"') do (
    for /f "tokens=*" %%c in ('wmic process where "ProcessId=%%p" get CommandLine /value 2^>nul ^| findstr /i "session_converter_web.py"') do set "RUNNING=1"
)
exit /b 0

:KILL_SERVER
echo [提示] 正在结束服务进程...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8765 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8766 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr /i "PID:"') do (
    for /f "tokens=*" %%c in ('wmic process where "ProcessId=%%p" get CommandLine /value 2^>nul ^| findstr /i "session_converter_web.py"') do taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul
exit /b 0

:START_SERVER
echo [提示] 正在启动服务...
echo        前台 http://127.0.0.1:!PORT!/
echo        后台 http://127.0.0.1:!PORT!/admin
start "" /B python tools\session_converter_web.py --host 127.0.0.1 --port !PORT! 1>>"data\server.log" 2>>"data\server.err.log"
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "try { $h=Invoke-RestMethod -Uri 'http://127.0.0.1:!PORT!/api/admin/health' -TimeoutSec 8; Write-Host '[成功] 健康检查通过 buildId=' $h.buildId } catch { Write-Host '[错误] 健康检查失败' $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo [提示] 请查看 data\server.log 和 data\server.err.log
)
exit /b 0

endlocal
exit /b 0
"""

out = Path(__file__).resolve().parent / "restart_admin.bat"
out.write_text(bat, encoding="gbk")
print("written", out)
