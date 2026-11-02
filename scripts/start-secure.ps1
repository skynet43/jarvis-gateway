$ErrorActionPreference = 'Stop'
$env:JARVIS_ADMIN_TOKEN = [Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')
if (-not $env:JARVIS_ADMIN_TOKEN) { throw 'Configure JARVIS_ADMIN_TOKEN in user environment first' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $root 'src\gateway.py')
