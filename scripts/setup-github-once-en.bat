@echo off
title Codex GitHub Setup
cd /d "%~dp0.."
echo ========================================
echo   Codex - GitHub one-time setup
echo ========================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo [X] Git not found
    echo     Install: https://git-scm.com/download/win
    pause
    exit /b 1
)
echo [OK] Git installed
git --version
echo.

git config --global user.name 2>nul | findstr /r "." >nul
if errorlevel 1 (
    echo [!] user.name not set
    set /p GNAME=GitHub username e.g. Aze0920:
    git config --global user.name "!GNAME!"
) else (
    echo [OK] user.name:
    git config --global user.name
)

git config --global user.email 2>nul | findstr /r "." >nul
if errorlevel 1 (
    echo [!] user.email not set
    set /p GEMAIL=GitHub email:
    git config --global user.email "!GEMAIL!"
) else (
    echo [OK] user.email:
    git config --global user.email
)
echo.

echo Open browser to create Personal Access Token:
echo   https://github.com/settings/tokens
echo   Check scope: repo
echo.
start "" "https://github.com/settings/tokens"
echo Save the token. On first push:
echo   Username = your GitHub name
echo   Password = paste TOKEN not login password
echo.
echo Daily upload: double-click scripts\push-to-github.bat
echo.
pause
