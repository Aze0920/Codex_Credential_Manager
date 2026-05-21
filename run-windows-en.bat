@echo off
title Codex Credential Manager
cd /d "%~dp0"

set "PYCMD=python"
where python >nul 2>&1 || (where py >nul 2>&1 && set "PYCMD=py -3")

%PYCMD% -c "import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ required
    pause
    exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating .venv ...
    %PYCMD% -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt -q
if not exist "data" mkdir "data"

if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

echo.
echo Front: http://127.0.0.1:8766
echo Admin: http://127.0.0.1:8766/admin
echo.

python tools\session_converter_web.py --host 127.0.0.1 --port 8766
pause
