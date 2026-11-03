param(
 [string[]]$Roots,
 [string[]]$Executables,
 [int]$Port = 18798
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Roots) { $Roots = @($root) }
if (-not $Executables) { $Executables = @((Join-Path $env:WINDIR 'System32\notepad.exe')) }
$Roots = @($Roots | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
$Executables = @($Executables | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
 throw "Port $Port already has a listener; review it before starting the adapter."
}
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$env:JARVIS_AUTOMATION_SECRET = [Convert]::ToBase64String($bytes)
$env:JARVIS_AUTOMATION_ROOTS = $Roots -join [IO.Path]::PathSeparator
$env:JARVIS_AUTOMATION_EXECUTABLES = $Executables -join [IO.Path]::PathSeparator
$env:JARVIS_AUTOMATION_PORT = [string]$Port
$env:JARVIS_AUTOMATION_URL = "http://127.0.0.1:$Port/mcp"
$work = Join-Path $root 'work'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$start = @{
 FilePath = Join-Path $root '.venv\Scripts\python.exe'
 ArgumentList = @('-m','adapter.automation_adapter')
 WorkingDirectory = $root
 WindowStyle = 'Hidden'
 PassThru = $true
 RedirectStandardOutput = Join-Path $work "automation-adapter-$Port.out.log"
 RedirectStandardError = Join-Path $work "automation-adapter-$Port.err.log"
}
$process = Start-Process @start
[pscustomobject]@{
 ProcessId = $process.Id
 Url = $env:JARVIS_AUTOMATION_URL
 Roots = $Roots
 Executables = $Executables
}
