# Codex - GitHub one-time setup (PowerShell, no CMD encoding issues)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Step([string]$t) { Write-Host $t -ForegroundColor Cyan }
function Write-Ok([string]$t) { Write-Host "[OK] $t" -ForegroundColor Green }
function Write-Warn([string]$t) { Write-Host "[!] $t" -ForegroundColor Yellow }

Write-Host ""
Write-Host "========================================" -ForegroundColor White
Write-Host "  Codex - GitHub one-time setup" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[X] Git not installed" -ForegroundColor Red
    Write-Host "    https://git-scm.com/download/win"
    exit 1
}
Write-Ok "Git: $(git --version)"
Write-Host ""

$name = (git config --global user.name 2>$null)
if ($name -match '^\!GNAME\!$' -or $name -match '^\s*$') { $name = $null }
if (-not $name) {
    Write-Warn "user.name not set"
    Write-Host "Enter GitHub USERNAME (not email). Example: Aze0920"
    $name = Read-Host "Username"
    $name = $name.Trim()
    if (-not $name) {
        Write-Host "[X] Username cannot be empty" -ForegroundColor Red
        exit 1
    }
    git config --global user.name $name
}
Write-Ok "user.name = $name"

$email = (git config --global user.email 2>$null)
if (-not $email) {
    Write-Warn "user.email not set"
    Write-Host "Enter email (GitHub account email or noreply address)"
    $email = Read-Host "Email"
    $email = $email.Trim()
    if (-not $email) {
        Write-Host "[X] Email cannot be empty" -ForegroundColor Red
        exit 1
    }
    git config --global user.email $email
}
Write-Ok "user.email = $email"
Write-Host ""

Write-Step "Create Personal Access Token in browser (scope: repo)"
Write-Host "  https://github.com/settings/tokens"
Start-Process "https://github.com/settings/tokens"
Write-Host ""
Write-Host "Save the token. When you run push-to-github.bat:"
Write-Host "  Username = $name"
Write-Host "  Password = paste TOKEN (not GitHub login password)"
Write-Host ""
Write-Host "Next: double-click scripts\push-to-github.bat" -ForegroundColor Green
Write-Host ""
