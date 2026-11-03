param([ValidateRange(1024,65535)][int]$Port=8765)
$ErrorActionPreference='Stop'
$url="http://127.0.0.1:$Port/dashboard"
$edgePaths=@("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe","$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")
$edge=$edgePaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) { throw 'Microsoft Edge is required for the desktop app window.' }
# This visible window is the user-facing Command Center.
Start-Process -FilePath $edge -ArgumentList "--app=$url"
