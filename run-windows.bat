@echo off
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
    echo [����] ��Ҫ Python 3.10 ����߰汾
    %PYCMD% --version 2>nul
    echo ����: https://www.python.org/downloads/
    pause
    exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
    echo [����] δ�ҵ� node��Sentinel ���ܲ�����
    echo ��װ Node 16+: https://nodejs.org/
)

if not exist ".venv\Scripts\activate.bat" (
    echo [��ʾ] �������⻷�� .venv ...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo [����] ���� venv ʧ��
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [����] ������װʧ�ܣ���������
    pause
    exit /b 1
)

if not exist "data" mkdir "data"

if "%ADMIN_PASSWORD%"=="" set "ADMIN_PASSWORD=admin123"

echo.
echo ǰ̨: http://127.0.0.1:8766
echo ��̨: http://127.0.0.1:8766/admin
echo ����: �������� ADMIN_PASSWORD ��Ĭ�� admin123
echo ����: �رձ����ڣ������� tools\restart_admin.bat
echo.

python tools\session_converter_web.py --host 127.0.0.1 --port 8766
pause
