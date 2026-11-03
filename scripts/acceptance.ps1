param([string]$Base='http://127.0.0.1:8765')
$ErrorActionPreference='Stop'
$headers=@{'X-Jarvis-Token'=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')}
$job=Invoke-RestMethod "$Base/control/jobs" -Method Post -Headers $headers -ContentType 'application/json' -Body (@{agent='rosie';prompt='Respond with the single word READY'}|ConvertTo-Json)
$deadline=(Get-Date).AddSeconds(150)
do {
 Start-Sleep -Milliseconds 500
 $current=Invoke-RestMethod "$Base/control/jobs/$($job.id)" -Headers $headers
} while ($current.status -in @('queued','running','cancelling') -and (Get-Date) -lt $deadline)
if ($current.status -ne 'completed' -or $current.result -notmatch 'READY') { throw "Inference acceptance failed: $($current.status)" }
Write-Output "INFERENCE_PASS job=$($job.id) output_saved=True"
