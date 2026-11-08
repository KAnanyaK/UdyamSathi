$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $python) { Write-Error 'Python is not on PATH. Install Python 3.11 and the packages in requirements.txt.' }
if (-not $npm) { Write-Error 'Node.js npm.cmd is not on PATH.' }
if (-not (Test-Path 'frontend/node_modules')) { & $npm --prefix frontend install }
$backend = Start-Process -FilePath $python -ArgumentList '-m uvicorn backend.main:app --reload --port 8000' -WorkingDirectory $root -PassThru -WindowStyle Hidden
try { & $npm --prefix frontend run dev } finally { Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue }
