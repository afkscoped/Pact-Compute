@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0pact-compute\scripts\demo.ps1" %*
exit /b %errorlevel%
