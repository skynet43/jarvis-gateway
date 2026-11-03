param([string]$Base='http://127.0.0.1:8765')
$ErrorActionPreference='Stop'
$h=@{'X-Jarvis-Token'=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')}
$job=Invoke-RestMethod "$Base/control/jobs" -Method Post -Headers $h -ContentType 'application/json' -Body (@{agent='benson';prompt='Print every integer from 1 through 10000, one per line. Begin now and do not summarize.'}|ConvertTo-Json)
$deadline=(Get-Date).AddSeconds(20)
do { Start-Sleep -Milliseconds 100; $current=Invoke-RestMethod "$Base/control/jobs/$($job.id)" -Headers $h } while ($current.status -eq 'queued' -and (Get-Date) -lt $deadline)
if ($current.status -ne 'running') { throw 'Task was not running at cancellation time' }
$timer=[Diagnostics.Stopwatch]::StartNew()
$null=Invoke-RestMethod "$Base/control/jobs/$($job.id)/cancel" -Method Post -Headers $h
do { Start-Sleep -Milliseconds 100; $current=Invoke-RestMethod "$Base/control/jobs/$($job.id)" -Headers $h } while ($current.status -eq 'cancelling' -and $timer.Elapsed.TotalSeconds -lt 15)
$timer.Stop()
if ($current.status -ne 'cancelled' -or -not $current.stream_closed) { throw 'Cancellation acknowledgement failed' }
Write-Output "CANCEL_PASS latency_ms=$([int]$timer.Elapsed.TotalMilliseconds) request_closed=True inference_stop=Unverified model_unload=False"
