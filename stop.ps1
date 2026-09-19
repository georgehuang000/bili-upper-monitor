<#
    B站 UP 主监控 —— 停止脚本（Windows / PowerShell 5.1+）

    停掉占用端口的后端进程，并清理可能残留的外层进程。

    为什么要"再扫一遍残留"：本机 venv 的 python.exe 可能是**重定向器**
    （先起一个同命令行的外层进程，再由它启动真正干活的子进程）。此时
    只杀"占用端口的那一个"会留下外层进程，反复启停会越堆越多。所以杀完
    端口占用者后，再按"本项目 venv + uvicorn main:app"精确清理一次。

    用法：stop.bat              停止默认端口 9000
          stop.bat -Port 9001   停止指定端口
#>
[CmdletBinding()]
param(
    [int]$Port = 9000
)

$ErrorActionPreference = 'Stop'

$VenvPy = Join-Path $PSScriptRoot 'server\.venv\Scripts\python.exe'

function Get-PortOwners([int]$p) {
    $owners = @()
    try {
        $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop
        $owners = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        $hits = & netstat -ano 2>$null | Select-String -Pattern ":$p\s+\S+\s+LISTENING"
        foreach ($h in $hits) {
            $parts = @(($h.ToString() -split '\s+') | Where-Object { $_ -ne '' })
            $last = $parts[-1]
            if ($last -match '^\d+$') { $owners += [int]$last }
        }
        $owners = @($owners | Select-Object -Unique)
    }
    return $owners
}

# 找本项目残留的 uvicorn 进程（避开系统里其它 python 程序）
function Get-OurLeftovers {
    $found = @()
    try {
        $found = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction Stop |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -like '*uvicorn*main:app*' -and
                ($_.CommandLine -like "*$VenvPy*" -or
                 ($_.ExecutablePath -and $_.ExecutablePath -eq $VenvPy))
            })
    } catch { }
    return $found
}

$owners = Get-PortOwners $Port
if ($owners.Count -eq 0) {
    $stray = Get-OurLeftovers
    if ($stray.Count -gt 0) {
        Write-Host "[停止] 端口 $Port 已空闲，但发现 $($stray.Count) 个残留后端进程，正在清理…" -ForegroundColor Yellow
    } else {
        Write-Host "[停止] 端口 $Port 上没有正在运行的服务" -ForegroundColor Yellow
        exit 0
    }
}

foreach ($ownerPid in $owners) {
    $name = '未知'
    try { $name = (Get-Process -Id $ownerPid -ErrorAction Stop).ProcessName } catch { }
    Write-Host "[停止] 结束 PID $ownerPid ($name) 及其子进程…" -ForegroundColor Cyan
    & taskkill /PID $ownerPid /T /F 2>$null | Out-Null
}

Start-Sleep -Milliseconds 1500

# 清理外层重定向进程等残留
$leftovers = Get-OurLeftovers
foreach ($lo in $leftovers) {
    Write-Host "[停止] 清理残留进程 PID $($lo.ProcessId)…" -ForegroundColor Cyan
    & taskkill /PID $lo.ProcessId /T /F 2>$null | Out-Null
}
if ($leftovers.Count -gt 0) { Start-Sleep -Milliseconds 800 }

$still = Get-PortOwners $Port
$remain = Get-OurLeftovers
if ($still.Count -eq 0 -and $remain.Count -eq 0) {
    Write-Host "   OK  已完全停止，端口 $Port 已释放" -ForegroundColor Green
    exit 0
} else {
    Write-Host "   失败 端口占用=$($still -join ',') 残留进程=$($remain.Count) 个，请到任务管理器手动结束" -ForegroundColor Red
    exit 1
}