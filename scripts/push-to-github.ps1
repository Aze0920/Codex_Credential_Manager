# Codex - push to GitHub
# See docs/GITHUB-PUSH.md
param(
    [string]$RemoteUrl = 'https://github.com/Aze0920/Codex_Credential_Manager.git',
    [string]$Branch = 'main',
    [string]$CommitMessage = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $ProjectRoot

function Write-Step([string]$Text) { Write-Host "[push] $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "[ok] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "[warn] $Text" -ForegroundColor Yellow }
function Write-Err([string]$Text) { Write-Host "[error] $Text" -ForegroundColor Red }

Write-Step "Project: $ProjectRoot"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err 'Git not installed. https://git-scm.com/download/win'
    exit 1
}

function Test-StagedSensitive {
    $patterns = @('\.db$', '\.log$', '^\.env$', '\.venv/', '^data/.*\.(db|log)$')
    $staged = @(git diff --cached --name-only 2>$null)
    foreach ($f in $staged) {
        foreach ($p in $patterns) {
            if ($f -match $p) { return $f }
        }
    }
    return $null
}

if (-not (Test-Path '.git')) {
    Write-Step 'git init'
    git init | Out-Null
}

if (-not $CommitMessage) {
    $ver = 'dev'
    if (Test-Path 'VERSION') {
        $ver = (Get-Content 'VERSION' -TotalCount 1).Trim()
    }
    $CommitMessage = "chore: sync Codex Credential Console v$ver"
}

Write-Step 'git add'
git add -A

$bad = Test-StagedSensitive
if ($bad) {
    Write-Err "Sensitive file would be committed: $bad"
    Write-Err 'Fix .gitignore then run: git reset HEAD'
    git reset HEAD -q 2>$null
    exit 1
}

Write-Step 'git status'
git status --short
$porcelain = git status --porcelain
if (-not $porcelain) {
    Write-Ok 'Nothing to commit'
    exit 0
}

Write-Step "git commit: $CommitMessage"
& git commit -m $CommitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Commit failed. Set user.name and user.email (see docs/GITHUB-PUSH.md)'
    exit 1
}

git branch -M $Branch 2>$null

$remotes = @(git remote 2>$null)
if ($remotes -contains 'origin') {
    git remote set-url origin $RemoteUrl | Out-Null
} else {
    git remote add origin $RemoteUrl
}

Write-Step "git push -> $RemoteUrl"
Write-Warn 'Login: username Aze0920, password = GitHub Token'
& git push -u origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Push failed. Check Token and docs/GITHUB-PUSH.md'
    exit 1
}

Write-Ok 'Push OK'
Write-Ok 'https://github.com/Aze0920/Codex_Credential_Manager'
