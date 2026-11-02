$ErrorActionPreference='Stop'
$base='http://127.0.0.1:8765/control/jobs'
$h=@{'X-Jarvis-Token'=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')}
$body=@{agent='benson';prompt='Write a very long detailed report of 3000 words about the history of computing.'} | ConvertTo-Json
$job=Invoke-RestMethod $base -Method Post -Headers $h -ContentType 'application/json' -Body $body
Write-Output ('JOB '+$job.id)
$running=$false
for($i=0;$i -lt 30;$i++){
 Start-Sleep -Milliseconds 500
 $items=(Invoke-WebRequest $base -Headers $h -UseBasicParsing).Content | ConvertFrom-Json
 $current=$items | Where-Object { $_.id -eq $job.id } | Select-Object -First 1
 if($current.status -eq 'running'){$running=$true;break}
}
if(-not $running){throw 'Job did not enter running state'}
Write-Output 'RUNNING_CONFIRMED'
$cancel=Invoke-RestMethod ($base+'/'+$job.id+'/cancel') -Method Post -Headers $h
Write-Output ('CANCEL '+$cancel.status)
Start-Sleep -Seconds 3
$items=(Invoke-WebRequest $base -Headers $h -UseBasicParsing).Content | ConvertFrom-Json
$current=$items | Where-Object { $_.id -eq $job.id } | Select-Object -First 1
Write-Output ('FINAL '+$current.status)
if($current.status -ne 'cancelled'){throw 'Cancellation status failed'}
