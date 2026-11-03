$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$token=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')
if (-not $token) { throw 'No existing user token is configured.' }
New-Item -ItemType Directory -Force (Join-Path $root 'data') | Out-Null
$token | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $root 'data\admin-token.dpapi')
$token=$null
Write-Output 'Saved a Windows DPAPI-protected token copy. Existing environment token was not removed or rotated.'
