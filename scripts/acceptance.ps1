$ErrorActionPreference='Stop'
$base='http://127.0.0.1:8765'
$headers=@{'X-Jarvis-Token'=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')}
$body=@{agent='rosie';prompt='Respond with the single word READY'} | ConvertTo-Json
$job=Invoke-RestMethod "$base/control/jobs" -Method Post -Headers $headers -ContentType 'application/json' -Body $body
Write-Output "CREATED $($job.id) $($job.status)"
for($i=0;$i -lt 30;$i++){
 Start-Sleep -Seconds 3
 $found=Invoke-RestMethod "$base/control/jobs" -Headers $headers | Where-Object id -eq $job.id
 Write-Output "POLL $i $($found.status)"
 if($found.status -in @('completed','failed','cancelled')){Write-Output "RESULT $($found.result)";break}
}
