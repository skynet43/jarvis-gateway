$ErrorActionPreference = 'Stop'
$modelRoot = [Environment]::GetEnvironmentVariable('OLLAMA_MODELS', 'User')
if (-not $modelRoot) { $modelRoot = 'E:\models' }
if (-not (Test-Path -LiteralPath $modelRoot -PathType Container)) {
    throw "Ollama model directory is missing: $modelRoot"
}
$env:OLLAMA_MODELS = $modelRoot
$env:OLLAMA_HOST = '127.0.0.1:11434'
$listener = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $tags = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    if (@($tags.models).name -notcontains 'tool-star-qwen:3b') {
        throw "Port 11434 is occupied by Ollama without Jarvis's selected model. Restart that instance with OLLAMA_MODELS=$modelRoot."
    }
    Write-Output "Ollama is ready with tool-star-qwen:3b from $modelRoot"
    exit 0
}
$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $ollama -PathType Leaf)) { throw 'Ollama executable is missing.' }
Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
Write-Output "Started local Ollama with models at $modelRoot"
