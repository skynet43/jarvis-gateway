$ErrorActionPreference='Stop'
$headers=@{'X-Jarvis-Token'=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')}
$agents=Invoke-RestMethod 'http://127.0.0.1:8765/control/agents' -Headers $headers
Write-Output ('AGENTS=' + $agents.Count)
$jobs=Invoke-RestMethod 'http://127.0.0.1:8765/control/jobs' -Headers $headers
Write-Output ('JOBS=' + @($jobs).Count)
$audit=Invoke-RestMethod 'http://127.0.0.1:8765/control/audit' -Headers $headers
Write-Output ('AUDIT=' + @($audit).Count)
