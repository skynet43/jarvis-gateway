# Jarvis Gateway

Local-first FastAPI control plane for the Skynet / Jarvis Command Center. The current implementation provides authenticated job submission, SQLite audit history, three named Ollama personas, a dark browser dashboard, and cooperative cancellation. **The personas are prompt configurations, not autonomous tool-using agents.**

## Requirements

- Python and dependencies from `requirements.txt`
- Optional Ollama at `http://127.0.0.1:11434`; current worker model: `tool-star-qwen:3b`
- Windows PowerShell for supplied acceptance scripts; NVIDIA GPU for the optional GPU probe

## Windows setup

```powershell
cd C:\Users\Codex\jarvis-gateway
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Configure a long random admin token in the Windows user environment.
[Environment]::SetEnvironmentVariable('JARVIS_ADMIN_TOKEN', '<replace-with-strong-random-secret>', 'User')
.\scripts\start-secure.ps1
```

Open `http://127.0.0.1:8765/dashboard`, enter the token, then click **Refresh**. Health endpoint: `http://127.0.0.1:8765/health`. The secure launcher reads the user environment token and binds to loopback. Keep the token private; do not commit it.

For Linux/macOS baseline startup, see `docs/SETUP.md` and `scripts/run-gateway.sh`. The authenticated control plane requires `JARVIS_ADMIN_TOKEN` in the server environment.

## Current API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health |
| `GET /dashboard` | Browser dashboard |
| `GET /control/agents` | Rosie, Benson, Mr. Belvedere |
| `POST /control/jobs` | Submit `{"agent":"rosie","prompt":"..."}` |
| `GET /control/jobs` | Recent jobs, statuses, results |
| `POST /control/jobs/{id}/cancel` | Cancel queued or running job |
| `GET /control/audit` | Recent audit records |

All `/control/*` operations require the `X-Jarvis-Token` header. Other Ollama proxy endpoints may have a different authentication policy and must not be exposed to untrusted networks.

## Tests

```powershell
.\.venv\Scripts\python.exe .\tests_control.py
.\scripts\smoke.ps1
.\scripts\cancel_acceptance.ps1
.\scripts\gpu_cancel_probe.ps1
```

Browser tests use Playwright and a separately installed Chromium browser: `scripts/browser_acceptance.py` and `scripts/browser_cancel.py`. See `docs/COMMAND_CENTER.md` for scope, limitations, and verification notes.

## Security and limitations

- Loopback binding only. Never expose port 8765 publicly without an independent security review.
- Jobs, outputs, and audit history persist in `data/jarvis.db`; the entire `data/` directory is ignored by git.
- Streaming cancellation is cooperative: cancellation status is persisted and checked between Ollama chunks. Immediate GPU process termination has **not** been conclusively proven.
- A prior probe observed GPU utilization fall from 78% to 1% five seconds after cancellation, while VRAM remained around 2.95 GiB and the model stayed loaded. This is not a VRAM-release claim.
- Current dashboard is a minimal HTML implementation. A full responsive GUI, accessibility improvements, typed API, and richer lifecycle tests remain planned.
- Do not treat named personas as authorized shell/file-system automation agents.

## Architecture and next steps

See `docs/COMMAND_CENTER.md` for the technical status, acceptance evidence, and prioritized GUI roadmap. Source: `src/gateway.py`, `src/control.py`, `src/worker.py`, `src/dashboard.html`.
