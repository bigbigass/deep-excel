[CmdletBinding()]
param(
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$devDir = Join-Path $repoRoot "outputs\dev"
$backendPidPath = Join-Path $devDir "backend.pid"
$frontendPidPath = Join-Path $devDir "frontend.pid"
$backendOutPath = Join-Path $devDir "backend.out.log"
$backendErrPath = Join-Path $devDir "backend.err.log"
$frontendOutPath = Join-Path $devDir "frontend.out.log"
$frontendErrPath = Join-Path $devDir "frontend.err.log"
$backendUrl = "http://127.0.0.1:8000/health"
$frontendUrl = "http://127.0.0.1:3000/"
$frontendApiBaseUrl = "http://127.0.0.1:8000"

function Remove-IfExists {
    param([string]$Path)

    if (Test-Path $Path) {
        Remove-Item $Path -Force
    }
}

function Get-PythonExecutable {
    $candidates = @(
        (Join-Path $repoRoot ".venv311\Scripts\python.exe"),
        (Join-Path $repoRoot ".venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Python virtual environment not found. Prepare .venv311 or .venv first."
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
        }

        Start-Sleep -Milliseconds 500
    }

    return $false
}

function Show-LogTail {
    param(
        [string]$Label,
        [string]$Path
    )

    Write-Host "--- $Label ---"
    if (Test-Path $Path) {
        Get-Content $Path -Tail 40
    }
    else {
        Write-Host "Log file not found: $Path"
    }
}

New-Item -ItemType Directory -Force -Path $devDir | Out-Null

$stopScript = Join-Path $PSScriptRoot "stop-local.ps1"
if ($ForceRestart -or (Test-Path $backendPidPath) -or (Test-Path $frontendPidPath)) {
    & $stopScript
}

$pythonExe = Get-PythonExecutable
$nextCmd = Join-Path $repoRoot "web\node_modules\.bin\next.cmd"
$powershellExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $nextCmd)) {
    throw "Missing $nextCmd. Run: cd web; npm install"
}

if (-not (Test-Path (Join-Path $repoRoot ".env"))) {
    Write-Warning "Missing .env at repo root. Backend will use defaults and upstream may be unconfigured."
}

Remove-IfExists $backendOutPath
Remove-IfExists $backendErrPath
Remove-IfExists $frontendOutPath
Remove-IfExists $frontendErrPath

$backendProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @(
        "-m",
        "uvicorn",
        "api.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload"
    ) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $backendOutPath `
    -RedirectStandardError $backendErrPath `
    -PassThru

$frontendCommand = @(
    "`$env:NEXT_PUBLIC_API_BASE_URL='$frontendApiBaseUrl'",
    "& '$nextCmd' dev --hostname 127.0.0.1 --port 3000"
) -join "; "

$frontendProcess = Start-Process `
    -FilePath $powershellExe `
    -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        $frontendCommand
    ) `
    -WorkingDirectory (Join-Path $repoRoot "web") `
    -RedirectStandardOutput $frontendOutPath `
    -RedirectStandardError $frontendErrPath `
    -PassThru

Set-Content -Path $backendPidPath -Value $backendProcess.Id -Encoding ascii
Set-Content -Path $frontendPidPath -Value $frontendProcess.Id -Encoding ascii

$backendReady = Wait-HttpReady -Url $backendUrl -TimeoutSeconds 60
if (-not $backendReady) {
    Show-LogTail -Label "backend.err.log" -Path $backendErrPath
    Show-LogTail -Label "backend.out.log" -Path $backendOutPath
    & $stopScript
    throw "Backend failed to become healthy within 60 seconds at $backendUrl."
}

$frontendReady = Wait-HttpReady -Url $frontendUrl -TimeoutSeconds 60
if (-not $frontendReady) {
    Show-LogTail -Label "frontend.err.log" -Path $frontendErrPath
    Show-LogTail -Label "frontend.out.log" -Path $frontendOutPath
    & $stopScript
    throw "Frontend failed to become reachable within 60 seconds at $frontendUrl."
}

Write-Host "Local dev environment is up."
Write-Host "- Backend: $backendUrl"
Write-Host "- Frontend: $frontendUrl"
Write-Host "- Backend PID: $($backendProcess.Id)"
Write-Host "- Frontend PID: $($frontendProcess.Id)"
Write-Host "- Log directory: $devDir"
Write-Host "Stop command: powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1"
