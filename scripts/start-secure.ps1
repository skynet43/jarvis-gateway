$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$protected = Join-Path $root 'data\admin-token.dpapi'
if (Test-Path -LiteralPath $protected) {
 $secure = Get-Content -LiteralPath $protected | ConvertTo-SecureString
 $handle = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
 try { $env:JARVIS_ADMIN_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($handle) }
 finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($handle) }
} else {
 $env:JARVIS_ADMIN_TOKEN = [Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')
}
if (-not $env:JARVIS_ADMIN_TOKEN) { throw 'Configure JARVIS_ADMIN_TOKEN or a DPAPI-protected token first.' }
if (-not (Test-Path (Join-Path $root 'frontend\dist\index.html'))) { throw 'Build the frontend first: cd frontend; npm ci; npm run build' }
$env:JARVIS_DB = Join-Path $root 'data\jarvis.db'
$env:JARVIS_HTTPS_ORIGIN = [Environment]::GetEnvironmentVariable('JARVIS_HTTPS_ORIGIN','User')
$ts=Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if ($env:JARVIS_HTTPS_ORIGIN -and (Test-Path -LiteralPath $ts)) {
 $tailnet=& $ts status --json | ConvertFrom-Json
 if ($tailnet.BackendState -eq 'Running' -and $env:JARVIS_HTTPS_ORIGIN -eq ('https://'+$tailnet.Self.DNSName.TrimEnd('.'))) {
  $env:JARVIS_TAILSCALE_LOGIN=$tailnet.User.($tailnet.Self.UserID).LoginName
 }
}
$adapter = . (Join-Path $PSScriptRoot 'start-automation-adapter.ps1') -Port 18798 -Roots @($root)
try {
 & (Join-Path $root '.venv\Scripts\python.exe') (Join-Path $root 'src\gateway.py')
} finally {
 if ($adapter -and (Get-Process -Id $adapter.ProcessId -ErrorAction SilentlyContinue)) {
  Stop-Process -Id $adapter.ProcessId
 }
}
