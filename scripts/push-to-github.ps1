# Codex - push to GitHub (run from Desktop\scripts or project\scripts)
param(
    [string]$RemoteUrl = 'https://github.com/Aze0920/Codex_Credential_Manager.git',
    [string]$Branch = 'main',
    [string]$CommitMessage = ''
)

$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
    $cfg = Join-Path $PSScriptRoot 'project-root.txt'
    if (Test-Path $cfg) {
        $line = (Get-Content $cfg -TotalCount 1 -ErrorAction SilentlyContinue)
        if ($line) {
            $p = $line.Trim()
            if (Test-Path $p) {
                return (Resolve-Path $p).Path
            }
            throw "project-root.txt points to missing folder: $p"
        }
    }
    $try = @(
        (Join-Path $PSScriptRoot '..\GPTSessionWeb_Source'),
        (Join-Path $PSScriptRoot '..')
    )
    foreach ($p in $try) {
        if ((Test-Path $p) -and (Test-Path (Join-Path $p 'VERSION'))) {
            return (Resolve-Path $p).Path
        }
    }
    throw "Cannot find project. Edit scripts\project-root.txt (one line = full path to GPTSessionWeb_Source)"
}

$ProjectRoot = Get-ProjectRoot
Set-Location $ProjectRoot

function Write-Step([string]$Text) { Write-Host "[push] $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "[ok] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "[warn] $Text" -ForegroundColor Yellow }
function Write-Err([string]$Text) { Write-Host "[error] $Text" -ForegroundColor Red }

Write-Step "Script folder: $PSScriptRoot"
Write-Step "Project folder: $ProjectRoot"

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
    Write-Err 'Commit failed. Run setup-github-once.bat'
    exit 1
}

git branch -M $Branch 2>$null

$tokenFile = Join-Path $PSScriptRoot '.github-token'
$token = $null
if (Test-Path $tokenFile) {
    $token = (Get-Content $tokenFile -Raw).Trim()
}

$remotes = @(git remote 2>$null)
if ($remotes -contains 'origin') {
    git remote set-url origin $RemoteUrl | Out-Null
} else {
    git remote add origin $RemoteUrl
}

$reject = "protocol=https`nhost=github.com`n`n"
$reject | git credential reject 2>$null | Out-Null

Write-Step "git push -> $RemoteUrl"
if ($token) {
    Write-Ok "Token: $tokenFile"
    $pushUrl = "https://Aze0920:$token@github.com/Aze0920/Codex_Credential_Manager.git"
    & git -c credential.helper= push $pushUrl $Branch
} else {
    Write-Warn "No token file. Run: $PSScriptRoot\save-github-token.bat"
    & git push -u origin $Branch
}
if ($LASTEXITCODE -ne 0) {
    Write-Err 'Push failed. Use CLASSIC token + repo scope, then save-github-token.bat'
    exit 1
}

Write-Ok 'Push OK'
Write-Ok 'https://github.com/Aze0920/Codex_Credential_Manager'
