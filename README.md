# Jarvis Gateway

Jarvis Gateway is the local AI control layer for CodexOS.

It connects Codex, Ollama, Unreal Engine, MetaHumans, automation, hardware workflows, and app bridge services through local-first APIs and safe integration points.

## Main folders

- `.agents/skills/` — repo-local Codex skills for Jarvis Gateway, app bridge work, and security review.
- `docs/` — setup and operating documentation.
- `scripts/` — local helper scripts for running and maintaining the gateway.
- `src/` — Jarvis Gateway source code.

## Local ports

| Service | Address |
| --- | --- |
| Jarvis Gateway | `127.0.0.1:8765` |
| Ollama | `127.0.0.1:11434` |
| AI Studio API | `127.0.0.1:8787` |

Jarvis Gateway is intended to bind to `127.0.0.1` by default. Do not expose it publicly unless that is an intentional, reviewed change.

## Quick start

```powershell
cd C:\Users\Administrator\Documents\GitHub\jarvis-gateway
.\scripts\run-gateway.ps1
```

Then open <http://127.0.0.1:8765/health>.
