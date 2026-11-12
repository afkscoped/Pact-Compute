$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$registry = Join-Path $projectRoot '.local\logs\processes.json'
if (-not (Test-Path -LiteralPath $registry)) { return }
$entries = @(Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json)
[array]::Reverse($entries)
foreach ($entry in $entries) {
    $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -eq $entry.process_name -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $entry.start) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
            throw "Could not stop $($entry.name)."
        }
        Write-Output "Stopped $($entry.name)."
    }
}
Remove-Item -LiteralPath $registry
