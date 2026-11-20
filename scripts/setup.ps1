# One-time setup for Windows PowerShell:  .\scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" scripts\make_env.py
& ".\.venv\Scripts\python.exe" seed.py --create-tables
Set-Location "$root\frontend"
npm install
Write-Host "`nSetup complete. Start everything with .\scripts\dev.ps1" -ForegroundColor Green
