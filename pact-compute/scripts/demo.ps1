param([switch]$Stop, [switch]$NoGpu, [switch]$Refresh, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv-demo\Scripts\python.exe'
$appPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $appPython)) { $appPython = $python }
if ($Stop) {
    if (Test-Path $appPython) { & $appPython scripts/demo.py --stop; exit $LASTEXITCODE }
    exit 0
}
$arguments = @('scripts/demo.py')
if ($NoGpu) { $arguments += '--no-gpu' }
if ($NoBrowser) { $arguments += '--no-browser' }
if (-not $Refresh -and (Test-Path -LiteralPath $appPython)) {
    & $appPython @arguments --open-existing
    if ($LASTEXITCODE -ne 3) { exit $LASTEXITCODE }
}
Write-Host 'Preparing PACT Compute. The website opens after the local services are ready.'
$tmp = Join-Path $root '.local\setup-tmp'
New-Item -ItemType Directory -Force $tmp | Out-Null
$env:TEMP = $tmp
$env:TMP = $tmp
if (-not (Test-Path $python)) {
    $base = $env:PACT_SETUP_PYTHON
    if (-not $base) {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if ($command) { $base = $command.Source }
    }
    if (-not $base -or (& $base -c 'import sys; print(sys.version_info[:2] == (3,12))') -ne 'True') {
        $bundle = Get-ChildItem 'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime*\dependencies\python\python.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($bundle) { $base = $bundle.FullName }
    }
    if (-not $base -or (& $base -c 'import sys; print(sys.version_info[:2] == (3,12))') -ne 'True') { throw 'Install Python 3.12, or set PACT_SETUP_PYTHON to its python.exe path.' }
    & $base -m venv .venv-demo
    if ($LASTEXITCODE) { throw 'Could not create the Python 3.12 demo environment.' }
}
$stamp = Join-Path $root '.venv-demo\setup.sha256'
$fingerprint = & $python -c "from pathlib import Path; import hashlib; print(''.join(hashlib.sha256(Path(p).read_bytes()).hexdigest().upper() for p in ['requirements-win-py312.lock.txt','requirements-gpu-win-py312.lock.txt']))"
if ($Refresh -or -not (Test-Path $stamp) -or (Get-Content $stamp -Raw).Trim() -ne $fingerprint) {
    & $python -m pip install -r requirements-win-py312.lock.txt
    if ($LASTEXITCODE) { throw 'Application dependency installation failed.' }
    & $python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-gpu-win-py312.lock.txt psutil==7.0.0
    if ($LASTEXITCODE) { throw 'GPU dependency installation failed.' }
    & $python -m pip check
    if ($LASTEXITCODE) { throw 'Dependencies are inconsistent.' }
    Set-Content -LiteralPath $stamp -Value $fingerprint
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 24 with npm and reopen the terminal.' }
Push-Location frontend
try {
    if ($Refresh -or -not (Test-Path node_modules)) {
        & npm.cmd ci
        if ($LASTEXITCODE) { throw 'Frontend dependency installation failed.' }
    }
    & npm.cmd run build
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
} finally { Pop-Location }
$env:PACT_DEMO_GPU_PYTHON = $python
& $appPython @arguments
exit $LASTEXITCODE
