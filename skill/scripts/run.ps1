<#
.SYNOPSIS
    DeepSeek Harness launcher: sets UTF-8, BOSS_WORK_DIR and the Python interpreter.

.DESCRIPTION
    DSH runs every pwsh call in a fresh process, so environment variables do not
    persist between calls. This script does the three error-prone things at once:
      1. Locate a usable Python (DSH bundled runtime first, then PATH).
      2. Set BOSS_WORK_DIR (all state files and the final report go there).
      3. Force UTF-8 console output so Chinese text is not mangled.

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step init
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step next-batch
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step read -Index 3
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step decide -Index 3
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Step evolve
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<SKILL_DIR>\scripts\run.ps1" -Script env_check.py
#>
[CmdletBinding()]
param(
    [string]$Script = 'serial_loop.py',
    [string]$Step = '',
    [int]$Index = 0,
    [string]$Keyword = '',
    [string]$WorkDir = '',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ExtraArgs
)

$ErrorActionPreference = 'Stop'

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

# ---- Working directory ------------------------------------------------
if (-not $WorkDir) {
    if ($env:BOSS_WORK_DIR) { $WorkDir = $env:BOSS_WORK_DIR }
    else { $WorkDir = (Get-Location).Path }
}
if (-not (Test-Path -LiteralPath $WorkDir)) {
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
}
$env:BOSS_WORK_DIR = (Resolve-Path -LiteralPath $WorkDir).Path

# ---- Python interpreter ----------------------------------------------
function Find-Python {
    if ($env:DSH_PYTHON -and (Test-Path -LiteralPath $env:DSH_PYTHON)) {
        return $env:DSH_PYTHON
    }

    $candidates = @()

    # DSH bundled runtime (enumerate because the runtime dir name may change)
    $runtimeRoot = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes'
    if (Test-Path -LiteralPath $runtimeRoot) {
        $candidates += Get-ChildItem -LiteralPath $runtimeRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName 'dependencies\python\python.exe' }
    }

    # python from PATH (skip the WindowsApps stub)
    $onPath = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($onPath -and $onPath.Source -and $onPath.Source -notmatch 'WindowsApps') {
        $candidates += $onPath.Source
    }

    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    throw 'Python not found. Call load_workspace_dependencies, then set $env:DSH_PYTHON to that python.exe and retry.'
}

$py = Find-Python
$target = Join-Path $PSScriptRoot $Script
if (-not (Test-Path -LiteralPath $target)) {
    throw "Script not found: $target"
}

# ---- Assemble arguments ----------------------------------------------
$argv = @()
if ($Step) { $argv += @('--step', $Step) }
if ($Index -gt 0) { $argv += @('--index', "$Index") }
if ($Keyword) { $argv += @('--keyword', $Keyword) }
if ($ExtraArgs) { $argv += $ExtraArgs }

Write-Host "[dsh] python  = $py" -ForegroundColor DarkGray
Write-Host "[dsh] workdir = $env:BOSS_WORK_DIR" -ForegroundColor DarkGray

& $py $target @argv
exit $LASTEXITCODE
