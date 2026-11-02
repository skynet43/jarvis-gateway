$ErrorActionPreference='Stop'
$base='http://127.0.0.1:8765/control/jobs'
$h=@{'X-Jarvis-Token'=[Environment]::GetEnvironmentVariable('JARVIS_ADMIN_TOKEN','User')}
$body=@{agent='benson';prompt='Write 3000 words explaining computing history in detail.'}|ConvertTo-Json
$job=Invoke-RestMethod $base -Method Post -Headers $h -ContentType 'application/json' -Body $body
Write-Output ('JOB='+$job.id)
for($i=0;$i -lt 40;$i++){
 Start-Sleep -Milliseconds 250
 $jobs=(Invoke-WebRequest $base -Headers $h -UseBasicParsing).Content|ConvertFrom-Json
 $j=$jobs|Where-Object id -eq $job.id|Select-Object -First 1
 if($j.status -eq 'running'){break}
}
if($j.status -ne 'running'){throw ('NOT_RUNNING '+$j.status)}
Write-Output 'RUNNING=YES'
Write-Output ('GPU_BEFORE='+((nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader) -join ''))
$null=Invoke-RestMethod ($base+'/'+$job.id+'/cancel') -Method Post -Headers $h
Start-Sleep -Seconds 5
$jobs=(Invoke-WebRequest $base -Headers $h -UseBasicParsing).Content|ConvertFrom-Json
$j=$jobs|Where-Object id -eq $job.id|Select-Object -First 1
Write-Output ('FINAL_STATUS='+$j.status)
Write-Output ('GPU_AFTER='+((nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader) -join ''))
Write-Output ('OLLAMA_LOADED='+(((Invoke-RestMethod 'http://127.0.0.1:11434/api/ps').models|Select-Object -ExpandProperty name) -join ','))
