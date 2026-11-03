$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:JARVIS_ADMIN_TOKEN = [Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')
if (-not $env:JARVIS_ADMIN_TOKEN) { throw 'Configure the admin token before starting.' }
$env:JARVIS_DB = Join-Path $root 'work\preview.db'
$env:JARVIS_HTTPS_ORIGIN = 'https://skynet.tail01ff2d.ts.net'
$ts=Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if (Test-Path -LiteralPath $ts) {
 $tailnet=& $ts status --json | ConvertFrom-Json
 if ($tailnet.BackendState -eq 'Running' -and $env:JARVIS_HTTPS_ORIGIN -eq ('https://'+$tailnet.Self.DNSName.TrimEnd('.'))) {
  $env:JARVIS_TAILSCALE_LOGIN=$tailnet.User.($tailnet.Self.UserID).LoginName
 }
}
Set-Location $root
$adapter = . (Join-Path $PSScriptRoot 'start-automation-adapter.ps1') -Port 18797 -Roots @($root)
try {
 & (Join-Path $root '.venv\Scripts\python.exe') -m uvicorn gateway:app --app-dir src --host 127.0.0.1 --port 8767 --log-level warning
} finally {
 if ($adapter -and (Get-Process -Id $adapter.ProcessId -ErrorAction SilentlyContinue)) {
  Stop-Process -Id $adapter.ProcessId
 }
}
