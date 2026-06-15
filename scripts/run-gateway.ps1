Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = "C:\Users\Administrator\Documents\GitHub\jarvis-gateway"
Set-Location -LiteralPath $RepoRoot

if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn requests pydantic
python .\src\gateway.py
