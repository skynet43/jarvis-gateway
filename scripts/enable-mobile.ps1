param([ValidateRange(1024,65535)][int]$Port=8767)
$ErrorActionPreference='Stop'
$ts=Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if (-not (Test-Path -LiteralPath $ts)) { throw 'Install and sign into Tailscale first.' }
$status=(& $ts status --json | ConvertFrom-Json)
if ($status.BackendState -ne 'Running') { throw 'Tailscale is not connected.' }
$existing=& $ts serve status --json | ConvertFrom-Json
if ($existing.Web) { throw 'An existing Serve configuration needs review before changing it.' }
$dns=$status.Self.DNSName.TrimEnd('.')
Write-Output "Private HTTPS origin: https://$dns"
Write-Output 'The gateway must allow this exact JARVIS_HTTPS_ORIGIN.'
& $ts serve --bg --https=443 "http://127.0.0.1:$Port"
if ($LASTEXITCODE -ne 0) { throw 'Tailscale Serve needs account HTTPS enablement or returned an error.' }
& $ts serve status
