param([switch]$NoGpu, [switch]$SkipImport)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend\dist\index.html'
$logDir = Join-Path $projectRoot '.local\logs'
$baseUrl = 'http://127.0.0.1:8765'

if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements.txt first.' }
if (-not (Test-Path -LiteralPath $frontend)) { throw 'Build the frontend with npm run build in frontend first.' }
$existing = $null
try { $existing = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2 } catch {}
if ($existing -and $existing.status -eq 'ok') { throw "PACT-Compute is already listening at $baseUrl." }

$null = New-Item -ItemType Directory -Path $logDir -Force
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
$env:PYTHONUNBUFFERED = '1'
Push-Location -LiteralPath $projectRoot
try {
    & $python -m pact.cli init
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed. Check the database configuration and migrations.' }
    if (-not $SkipImport) {
        & $python -m pact.cli import
        if ($LASTEXITCODE -ne 0) { throw 'Dataset import failed. Correct the source directory or start with -SkipImport.' }
    }
    $processes = [System.Collections.Generic.List[object]]::new()
    function Start-PactProcess([string]$name, [string[]]$arguments) {
        $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir "$name.log") -RedirectStandardError (Join-Path $logDir "$name.error.log")
        $processes.Add([pscustomobject]@{ name=$name; id=$process.Id; process_name=$process.ProcessName; start=$process.StartTime.ToUniversalTime().Ticks.ToString() })
        $processes.ToArray() | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDir 'processes.json')
    }
    Start-PactProcess 'api' @('-m', 'uvicorn', 'pact.api:app', '--host', '127.0.0.1', '--port', '8765')
    $ready = $false
    foreach ($attempt in 1..25) {
        try {
            $ready = (Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 2).status -eq 'ok'
            if ($ready) { break }
        } catch {}
        Start-Sleep -Milliseconds 350
    }
    if (-not $ready) { throw "API did not become healthy. Check $logDir\api.error.log." }
    Start-PactProcess 'worker' @('-m', 'pact.worker')
    if (-not $NoGpu) { Start-PactProcess 'runner' @('-m', 'pact.runner') }
    Write-Output "PACT-Compute is running at $baseUrl"
    Write-Output "Sign in as admin using the password in .local\local-credentials.json."
} finally {
    Pop-Location
}
