# Start API (new window) and web app (this window):  .\scripts\dev.ps1
$root = Split-Path -Parent $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\.venv\Scripts\python.exe wsgi.py"
Set-Location "$root\frontend"
npm run dev
