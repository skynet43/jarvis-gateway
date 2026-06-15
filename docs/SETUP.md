# Jarvis Gateway Setup

## Windows setup

Open PowerShell and run:

```powershell
cd C:\Users\Administrator\Documents\GitHub\jarvis-gateway
python -m venv .venv
.\.venv\Scripts\activate
pip install fastapi uvicorn requests pydantic
python .\src\gateway.py
```

Jarvis Gateway binds locally to `127.0.0.1:8765` and expects Ollama at `http://127.0.0.1:11434`.
