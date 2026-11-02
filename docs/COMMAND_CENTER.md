# Jarvis Command Center: Technical Status and GUI Roadmap

Updated: 2026-11-02

## Implemented

- FastAPI loopback gateway at `127.0.0.1:8765`.
- Authenticated `/control` endpoints with token supplied in `X-Jarvis-Token`.
- SQLite jobs, persisted model results, and audit events.
- Named personas Rosie, Benson, and Mr. Belvedere. These are **not** independent system-control agents.
- Background Ollama worker using model `tool-star-qwen:3b` and streaming chat responses.
- Queued and running job cancellation with database state protection.
- Basic dark HTML dashboard with job submission, cancellation, status polling, and audit.
- Secure Windows launcher `scripts/start-secure.ps1`.

## Acceptance evidence (2026-11-02)

| Check | Observed result |
| --- | --- |
| Backend regression | 7/7 pass |
| Browser dashboard submit | Pass in headless Chromium |
| Browser cancel | `BROWSER_CANCEL_PASS` |
| Running cancellation | `RUNNING_CONFIRMED`, `CANCEL cancelled`, `FINAL cancelled`, exit 0 |
| Ollama completion | Rosie job returned `READY`, persisted |
| GPU sample | 78% before cancel; 1% five seconds after |
| VRAM sample | 2,949 MiB before; 2,954 MiB after |
| Model residency | `tool-star-qwen:3b` still loaded |

GPU utilization is not exclusive proof of inference termination. VRAM was **not released**. Do not claim otherwise. Re-run all tests after subsequent changes.

## Known gaps and risks

1. Streaming cancellation may wait for another Ollama response chunk; latency and request closure need repeated measurement.
2. The dashboard does not yet display persisted model answers prominently or provide detailed job inspection.
3. Worker restart recovery, concurrent request handling, cancellation races, and timeout behavior need stronger tests.
4. Audit token handling and protection of non-control Ollama proxy routes need security review.
5. The current frontend is a single HTML file; no modern component system or typed client.
6. Live GPU telemetry, model unloading, SSE/WebSocket events, accessibility, and responsive layouts remain unimplemented.
7. There is no verified installer acceptance for this revision.

## Astra development brief

**Goal:** Inspect the existing repo and deliver a premium, production-quality Skynet / Jarvis Command Center without breaking working APIs.

### Phase A: Audit and harden
Inspect source, tests, dependencies, security, git diff, and launch scripts. Fix critical issues. Ensure no secrets, database files, or logs are committed. Validate loopback binding, auth, state transitions, and restart recovery.

### Phase B: GUI foundation
Use React + TypeScript + Vite or justify another maintainable stack. Build a responsive dark interface with accessible navigation, keyboard support, high-contrast typography, and restrained animation. Navigation: Overview, Agents, Tasks, Activity, Models, Connections, Security, Settings.

### Phase C: Live features
Wire actual agent jobs, output, cancellation, retries, event timeline, model inventory, and real GPU telemetry. Prefer SSE/WebSocket with reconnect and polling fallback. Clearly distinguish queued, running, cancelling, cancelled, completed, failed. Never invent progress percentages or connected-state badges.

### Phase D: Test and release
Run backend regression, browser E2E, accessibility checks, TypeScript typecheck, frontend build, security checks, and live Ollama acceptance. Include screenshots and exact test results. Build installer only after runtime acceptance and explicit approval.

## Required deliverables

- Updated working source in this repository.
- `ASTRA_AUDIT.md` with severity, file/line, reproduction, fix, and retest.
- `ASTRA_ACCEPTANCE.md` with exact commands, test results, and unresolved issues.
- README and operational docs updated to match verified behavior.
- No public exposure, remote deployment, or destructive changes without authorization.

## Local test commands

```powershell
.\.venv\Scripts\python.exe .\tests_control.py
.\scripts\smoke.ps1
.\scripts\cancel_acceptance.ps1
.\scripts\gpu_cancel_probe.ps1
```

Browser scripts: `scripts/browser_acceptance.py` and `scripts/browser_cancel.py` (requires Playwright and Chromium). The GPU probe requires NVIDIA utilities and a working Ollama model.
