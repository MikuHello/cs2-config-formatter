[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("check", "build", "quick", "release-local", "help")]
    [string]$Command = "help",
    [switch]$InstallWheel,
    [switch]$QuickCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Action
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        Write-Host "失败: $Name (退出码: $code)"
        exit $code
    }
    Write-Host "通过: $Name"
}

function Show-Usage {
    Write-Host @"
用法:
  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 <command> [选项]

命令:
  check         运行质量门（pytest + ruff + mypy）
  build         构建并校验分发包（uv build + twine check）
  quick         快速验证命令可用性（cfgfmt --help）
  release-local 执行本地分发流程（build + 可选安装 wheel + 可选快速验证）
  help          显示本帮助

选项:
  -InstallWheel  仅用于 release-local：安装 dist 里最新 wheel
  -QuickCheck    仅用于 release-local：执行快速验证

示例:
  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 check
  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 build
  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 quick
  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 release-local -InstallWheel -QuickCheck
"@
}

function Ensure-Uv {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "失败: 未检测到 uv，请先安装 uv。"
        exit 127
    }
}

function Invoke-Check {
    Invoke-Step -Name "运行测试 (pytest)" -Action { uv run pytest -q }
    Invoke-Step -Name "运行静态检查 (ruff)" -Action { uv run ruff check . }
    Invoke-Step -Name "运行类型检查 (mypy)" -Action { uv run mypy cfgfmt }
    Write-Host ""
    Write-Host "完成: 所有质量门均通过。"
}

function Invoke-Build {
    Invoke-Step -Name "构建分发包 (uv build)" -Action { uv build }
    Invoke-Step -Name "校验分发包元数据 (twine check)" -Action { uv run python -m twine check dist/* }
    Write-Host ""
    Write-Host "完成: 分发包构建与校验完成。"
}

function Install-LatestWheel {
    $wheel = Get-ChildItem -Path "dist" -Filter "*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $wheel) {
        Write-Host "失败: dist 目录下未找到 .whl 文件。"
        exit 2
    }

    Invoke-Step -Name "安装最新 wheel ($($wheel.Name))" -Action {
        uv pip install --force-reinstall $wheel.FullName
    }
}

function Invoke-QuickCheck {
    Invoke-Step -Name "快速验证: uv run cfgfmt --help" -Action { uv run cfgfmt --help }
    Invoke-Step -Name "快速验证: uv run cfgfmt format --help" -Action { uv run cfgfmt format --help }

    Write-Host ""
    Write-Host "完成: 快速验证通过。"
}

function Invoke-ReleaseLocal {
    Invoke-Step -Name "构建分发包 (uv build)" -Action { uv build }
    Invoke-Step -Name "校验分发包元数据 (twine check)" -Action { uv run python -m twine check dist/* }

    if ($InstallWheel) {
        Install-LatestWheel
    }

    if ($QuickCheck) {
        Invoke-QuickCheck
    }

    Write-Host ""
    Write-Host "完成: 本地分发流程执行结束。"
}

$scriptRoot = Split-Path -Parent $PSCommandPath
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..")
Push-Location $projectRoot
try {
    if ($Command -eq "help") {
        Show-Usage
        exit 0
    }

    Ensure-Uv

    switch ($Command) {
        "check" { Invoke-Check; break }
        "build" { Invoke-Build; break }
        "quick" { Invoke-QuickCheck; break }
        "release-local" { Invoke-ReleaseLocal; break }
        default { Show-Usage; exit 2 }
    }
}
finally {
    Pop-Location
}


