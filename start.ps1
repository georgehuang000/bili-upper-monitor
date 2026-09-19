<#
    B站 UP 主监控 —— 一键启动脚本（Windows / PowerShell 5.1+）

    做四件事：
      1. 检查环境：venv、Python 依赖、前端产物；缺什么补什么
      2. 前端源码比 dist 新时自动重建，避免网页显示旧界面
      3. 端口已被本服务占用时直接复用（不会重复启动）
      4. 启动后端 → 等健康检查通过 → 打开浏览器，日志落到 logs\

    用法：
      start.bat                  正常启动（推荐，双击即可）
      start.bat -Restart         先停掉已在运行的本服务再启动（改完代码用这个）
      start.bat -NoBuild         跳过前端重建检查（只动后端时更快）
      start.bat -NoBrowser       不自动打开浏览器
      start.bat -Foreground      前台运行（日志直接打在窗口里，Ctrl+C 停止）
      start.bat -Bind 0.0.0.0    监听所有网卡（局域网/公网访问用，注意安全）
#>
[CmdletBinding()]
param(
    [int]$Port = 9000,
    [string]$Bind = '127.0.0.1',
    [switch]$Restart,
    [switch]$NoBuild,
    [switch]$NoBrowser,
    [switch]$Foreground
)

$ErrorActionPreference = 'Stop'

# ── 路径 ──────────────────────────────────────────────
$Root      = $PSScriptRoot
$ServerDir = Join-Path $Root 'server'
$WebDir    = Join-Path $Root 'web'
$VenvPy    = Join-Path $ServerDir '.venv\Scripts\python.exe'
$LogDir    = Join-Path $Root 'logs'
$LogErr    = Join-Path $LogDir 'backend.log'      # 应用日志（uvicorn/爬虫都走 stderr）
$LogOut    = Join-Path $LogDir 'backend.stdout.log'
$BaseUrl   = "http://127.0.0.1:$Port"

function Info($m) { Write-Host "[启动] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "   OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "   ..  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "   失败 $m" -ForegroundColor Red }

function Get-PortOwners([int]$p) {
    $owners = @()
    try {
        $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop
        $owners = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        # 回退方案：Get-NetTCPConnection 不可用时用 netstat 解析
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

function Test-Ours([string]$url) {
    # 确认占用端口的是本项目（/api/status 返回带 crawling/uppers 的 JSON）
    try {
        $r = Invoke-WebRequest -Uri "$url/api/status" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -ne 200) { return $false }
        $j = $r.Content | ConvertFrom-Json
        return ($null -ne $j.crawling -and $null -ne $j.uppers)
    } catch {
        return $false
    }
}

function Stop-Ours([int]$p) {
    $owners = Get-PortOwners $p
    if (-not $owners -or $owners.Count -eq 0) { return $false }
    foreach ($ownerPid in $owners) {
        # /T 连子进程一起杀（爬虫子进程、Playwright 等）
        & taskkill /PID $ownerPid /T /F 2>$null | Out-Null
    }
    Start-Sleep -Milliseconds 1200
    return ((Get-PortOwners $p).Count -eq 0)
}

function Show-LogTail([string]$path, [int]$lines = 25) {
    if (-not (Test-Path $path)) { return }
    Write-Host "  ---- $path 最后 $lines 行 ----" -ForegroundColor DarkGray
    Get-Content -Path $path -Tail $lines -Encoding UTF8 -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
}

# ── 0. 前置检查 ───────────────────────────────────────
if (-not (Test-Path $ServerDir)) { Fail "找不到 server 目录：$ServerDir"; exit 1 }
if (-not (Test-Path (Join-Path $Root '.env'))) {
    Fail "根目录缺少 .env（需要配置 B站 Cookie 与 sensetime_key）"
    exit 1
}

# ── 1. 端口占用处理 ───────────────────────────────────
$existing = Get-PortOwners $Port
if ($existing.Count -gt 0) {
    if (Test-Ours $BaseUrl) {
        if ($Restart) {
            Info "端口 $Port 已被本服务占用（PID $($existing -join ',')），按 -Restart 要求先停止"
            if (Stop-Ours $Port) { Ok "已停止旧进程" } else { Fail "旧进程没能停掉，请手动处理"; exit 1 }
        } else {
            Ok "服务已在运行：$BaseUrl（PID $($existing -join ',')），不重复启动"
            if (-not $NoBrowser) { Start-Process $BaseUrl | Out-Null }
            exit 0
        }
    } else {
        Fail "端口 $Port 被其它程序占用（PID $($existing -join ',')）"
        Write-Host "       请先关掉它，或改用其它端口：start.bat -Port 9001" -ForegroundColor DarkGray
        exit 1
    }
}

# ── 2. Python 虚拟环境 ────────────────────────────────
if (-not (Test-Path $VenvPy)) {
    Warn "未找到 server\.venv，正在创建…"
    $sysPy = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $sysPy) { Fail "系统里没有 python，请先安装 Python 3.10+"; exit 1 }
    & python -m venv (Join-Path $ServerDir '.venv')
    Ok "虚拟环境已创建"
}

# 依赖自检：缺依赖（比如新增了 qrcode）就补装，省得启动后才发现
$depProbe = & $VenvPy -c "import fastapi, uvicorn, sqlalchemy, apscheduler, openai, dotenv, httpx, qrcode" 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "Python 依赖缺失，正在安装 requirements.txt…"
    & $VenvPy -m pip install -q -r (Join-Path $ServerDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { Fail "依赖安装失败，请手动执行 pip install -r server\requirements.txt"; exit 1 }
    Ok "依赖已安装"
} else {
    Ok "Python 依赖完整"
}

# ── 3. 前端产物 ───────────────────────────────────────
$DistIndex = Join-Path $WebDir 'dist\index.html'
function Test-NeedsBuild {
    if (-not (Test-Path $DistIndex)) { return $true }
    $distTime = (Get-Item $DistIndex).LastWriteTimeUtc
    $newer = Get-ChildItem (Join-Path $WebDir 'src') -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTimeUtc -gt $distTime }
    foreach ($f in @('index.html', 'package.json', 'vite.config.js')) {
        $p = Join-Path $WebDir $f
        if ((Test-Path $p) -and (Get-Item $p).LastWriteTimeUtc -gt $distTime) { return $true }
    }
    return ($null -ne $newer -and @($newer).Count -gt 0)
}

if ($NoBuild) {
    if (-not (Test-Path $DistIndex)) {
        Fail "web\dist 不存在且指定了 -NoBuild，请先执行 cd web; npm run build"
        exit 1
    }
    Ok "前端产物存在（已跳过重建检查）"
} elseif (Test-NeedsBuild) {
    Warn "前端有改动或产物缺失，正在重建…"
    $npm = (Get-Command npm -ErrorAction SilentlyContinue)
    if (-not $npm) { Fail "未找到 npm，无法重建前端；请装 Node.js 或加 -NoBuild"; exit 1 }
    if (-not (Test-Path (Join-Path $WebDir 'node_modules'))) {
        Warn "node_modules 缺失，先 npm install…"
        Push-Location $WebDir; & npm install; $code = $LASTEXITCODE; Pop-Location
        if ($code -ne 0) { Fail "npm install 失败"; exit 1 }
    }
    Push-Location $WebDir
    & npm run build
    $buildCode = $LASTEXITCODE
    Pop-Location
    if ($buildCode -ne 0) { Fail "前端构建失败，请看上面的报错"; exit 1 }
    Ok "前端已重建"
} else {
    Ok "前端产物是最新的，无需重建"
}

# ── 4. 启动后端 ───────────────────────────────────────
$uvArgs = @('-m', 'uvicorn', 'main:app', '--host', $Bind, '--port', "$Port")
$env:PYTHONIOENCODING = 'utf-8'   # 让子进程日志按 UTF-8 落盘，方便读取

if ($Foreground) {
    Info "前台启动（Ctrl+C 停止）：$BaseUrl"
    if (-not $NoBrowser) { Start-Process $BaseUrl | Out-Null }
    Push-Location $ServerDir
    & $VenvPy @uvArgs
    Pop-Location
    exit $LASTEXITCODE
}

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
# 上一轮日志留一份，方便对比
if (Test-Path $LogErr) {
    Move-Item -Path $LogErr -Destination "$LogErr.prev" -Force
}

Info "启动后端（监听 $Bind`:$Port）…"
$proc = Start-Process -FilePath $VenvPy -ArgumentList $uvArgs `
    -WorkingDirectory $ServerDir `
    -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr `
    -WindowStyle Hidden -PassThru

# 等健康检查通过
$deadline = (Get-Date).AddSeconds(40)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -Uri "$BaseUrl/api/status" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 700
}

if (-not $healthy) {
    Fail "后端启动失败（进程已退出：$($proc.HasExited)，退出码：$(try { $proc.ExitCode } catch { '未知' })）"
    Show-LogTail $LogErr
    exit 1
}

# ── 5. 打开浏览器 + 汇总 ──────────────────────────────
if (-not $NoBrowser) { Start-Process $BaseUrl | Out-Null }

$statusTxt = '未知'
try {
    $st = (Invoke-WebRequest -Uri "$BaseUrl/api/status" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
    if ($st.login_required) { $statusTxt = '已失效（请点顶栏「扫码登录」）' } else { $statusTxt = '有效' }
} catch { }

# 提示启动后会不会立刻跑一轮爬取。注意环境变量优先于 .env
# （python-dotenv 不覆盖已存在的环境变量），所以要按实际生效值判断
$autoCrawl = '否（等 08:00 / 18:00 定时任务，或手动点按钮）'
$autoCrawlRaw = $env:AUTO_CRAWL_ON_START
if (-not $autoCrawlRaw) {
    $envLine = Select-String -Path (Join-Path $Root '.env') -Pattern '^\s*AUTO_CRAWL_ON_START\s*=' -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($envLine) { $autoCrawlRaw = ($envLine.Line -split '=', 2)[1] }
}
if ($autoCrawlRaw -and $autoCrawlRaw.ToString().Trim() -match '^(true|1|yes)$') {
    $autoCrawl = '是（启动后立刻跑一轮，约数分钟，见日志）'
}

Write-Host ""
Ok "启动完成"
# 本机 venv 的 python.exe 可能是"重定向器"（外层 + 真正工作的内层），
# 真正监听端口的是内层进程，报它与任务管理器对得上
$shownPid = $proc.Id
$ownersNow = Get-PortOwners $Port
if ($ownersNow.Count -gt 0) { $shownPid = $ownersNow[0] }
Write-Host "   访问地址 : $BaseUrl"
Write-Host "   进程 PID : $shownPid"
Write-Host "   B站登录态: $statusTxt"
Write-Host "   自动爬取 : $autoCrawl"
Write-Host "   运行日志 : $LogErr"
Write-Host "   停止服务 : 双击 stop.bat（或结束 PID $shownPid）"
Write-Host "   诊断快照 : $BaseUrl/api/diagnostics" -ForegroundColor DarkGray