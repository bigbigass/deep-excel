[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$devDir = Join-Path $repoRoot "outputs\dev"
$backendPidPath = Join-Path $devDir "backend.pid"
$frontendPidPath = Join-Path $devDir "frontend.pid"

function Stop-RecordedProcess {
    param(
        [string]$Name,
        [string]$PidFilePath
    )

    if (-not (Test-Path $PidFilePath)) {
        Write-Host "$Name pid file not found."
        return
    }

    $rawPid = (Get-Content $PidFilePath -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not $rawPid) {
        Remove-Item $PidFilePath -Force
        Write-Host "$Name pid file was empty and has been removed."
        return
    }

    $process = Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue
    if ($process) {
        & taskkill /PID $rawPid /T /F | Out-Null
        Write-Host "Stopped $Name process: $rawPid"
    }
    else {
        Write-Host "$Name process not found: $rawPid"
    }

    Remove-Item $PidFilePath -Force
}

Stop-RecordedProcess -Name "backend" -PidFilePath $backendPidPath
Stop-RecordedProcess -Name "frontend" -PidFilePath $frontendPidPath
