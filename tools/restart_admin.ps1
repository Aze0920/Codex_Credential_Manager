param(
    [ValidateSet("start", "stop", "restart")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$port = 8766
$root = Split-Path -Parent $PSScriptRoot
$logOut = Join-Path $root "data\server.log"
$logErr = Join-Path $root "data\server.err.log"
$serverUrl = "http://127.0.0.1:$port/"
$adminUrl = "http://127.0.0.1:$port/admin"

function Get-ServerProcessIds {
    $pids = New-Object 'System.Collections.Generic.HashSet[int]'
    foreach ($p in @(8765, 8766)) {
        Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            Where-Object { $_ -and $_ -gt 0 } |
            ForEach-Object { [void]$pids.Add([int]$_) }
    }
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*session_converter_web.py*" } |
        ForEach-Object { [void]$pids.Add([int]$_.ProcessId) }
    return @($pids)
}

function Test-ServerRunning {
    return (Get-ServerProcessIds).Count -gt 0
}

function Stop-Server {
    $pids = Get-ServerProcessIds
    if (-not $pids.Count) {
        Write-Host "[提示] 没有发现正在运行的服务"
        return $false
    }
    foreach ($procId in $pids) {
        Write-Host "[提示] 正在结束进程 PID $procId"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
    if (Test-ServerRunning) {
        Write-Host "[警告] 部分进程还在退出, 请稍后再试"
        return $false
    }
    Write-Host "[成功] 服务已结束"
    return $true
}

function Start-Server {
    if (Test-ServerRunning) {
        Write-Host "[警告] 服务已在运行, 请选择 [1] 重启"
        return $false
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $root "data") | Out-Null
    Set-Location $root
    Write-Host "[提示] 正在启动"
    Write-Host "       前台 $serverUrl"
    Write-Host "       后台 $adminUrl"
    $proc = Start-Process -FilePath "python" `
        -ArgumentList "tools/session_converter_web.py", "--host", "127.0.0.1", "--port", "$port" `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logOut `
        -RedirectStandardError $logErr `
        -PassThru
    Write-Host "[成功] 已启动 PID $($proc.Id)"
    Write-Host "[提示] 日志 $logOut"
    Start-Sleep -Seconds 2
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/admin/health" -TimeoutSec 8
        Write-Host "[成功] 健康检查通过 buildId=$($health.buildId)"
        return $true
    }
    catch {
        Write-Host "[错误] 健康检查失败 $($_.Exception.Message)"
        if (Test-Path $logOut) { Get-Content $logOut -Tail 20 }
        if (Test-Path $logErr) { Get-Content $logErr -Tail 20 }
        return $false
    }
}

function Restart-Server {
    Stop-Server | Out-Null
    return Start-Server
}

function Show-Menu {
    $running = Test-ServerRunning
    Write-Host ""
    Write-Host "========================================"
    Write-Host " Codex凭证管理 服务管理"
    Write-Host "========================================"
    if ($running) {
        Write-Host "当前状态: 运行中"
        Write-Host "访问地址: $serverUrl"
        Write-Host "后台地址: $adminUrl"
        Write-Host ""
        Write-Host " [1] 重启服务"
        Write-Host " [2] 结束服务"
        Write-Host " [0] 退出"
    }
    else {
        Write-Host "当前状态: 未运行"
        Write-Host ""
        Write-Host " [1] 启动服务"
        Write-Host " [0] 退出"
    }
    Write-Host ""
    return Read-Host "请输入选项"
}

function Invoke-SelectedAction {
    param([string]$Choice, [bool]$Running)
    if ($Running) {
        switch ($Choice) {
            "1" { return Restart-Server }
            "2" { return Stop-Server }
            "0" { Write-Host "[提示] 已取消"; return $true }
            default { Write-Host "[警告] 无效选项"; return $null }
        }
    }
    switch ($Choice) {
        "1" { return Start-Server }
        "0" { Write-Host "[提示] 已取消"; return $true }
        default { Write-Host "[警告] 无效选项"; return $null }
    }
}

function Main {
    if ($Action) {
        switch ($Action) {
            "start" { if (-not (Start-Server)) { exit 1 }; return }
            "stop" { if (-not (Stop-Server)) { exit 1 }; return }
            "restart" { if (-not (Restart-Server)) { exit 1 }; return }
        }
    }
    while ($true) {
        $running = Test-ServerRunning
        $choice = Show-Menu
        $result = Invoke-SelectedAction -Choice $choice -Running $running
        if ($null -eq $result) { continue }
        break
    }
}

Main
