# Jarvis Gateway

Jarvis is a Windows-first, loopback FastAPI control center with a React dashboard, SQLite task history, local Ollama inference, supervised source-reading runtime sessions, transient model-provider connections, and local MCP tool discovery with one-use approvals.

## Start on Windows

```powershell
cd C:\Users\Codex\jarvis-gateway
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
# Set a long random JARVIS_ADMIN_TOKEN in the Windows user environment.
.\scripts\start-secure.ps1
```

Open `http://127.0.0.1:8765/dashboard`. The browser connects automatically on this laptop through a short-lived HttpOnly cookie; the admin token stays on the server. A running preview on port 8767 uses `scripts/start-preview.ps1` and a separate database. On a fresh database, no agents are active until selected in **Agents**. Existing databases with tasks preserve the original Rosie, Benson, and Mr. Belvedere templates.

The current selected Ollama model is `tool-star-qwen:3b`. Keep the model the user selected. On Skynet, set `OLLAMA_MODELS=E:\models` in the Ollama process environment and bind it to `127.0.0.1:11434`. `scripts/start-ollama-local.ps1` checks for an existing listener and does not replace one silently. `JARVIS_OLLAMA_URL` optionally points all gateway components at another loopback Ollama instance.

## Connections and permissions

**Connections** lists Ollama, LM Studio, llama.cpp, vLLM, OpenAI, Anthropic, Gemini, OpenRouter, Groq, Mistral, xAI and a custom local OpenAI-compatible API. A successful connection fetches available models. The selected connected model can receive a prompt through `/control/providers/{provider}/chat`. API keys stay only in gateway process memory, are cleared from the browser form after connection, and are lost on restart. Hosted API endpoints are fixed; local endpoints must use loopback. Provider calls use the provider's API and may incur its charges.

Local MCP Streamable HTTP servers can be connected from **Connections**. Their tool schemas are shown before use. Each exact tool call requires a one-use approval and is audited. MCP server connections and pending approvals are process-memory state and disappear on restart. Do not treat remote or untrusted MCP servers as supported by this local-only connection flow.

The supervised Ollama runtime can list and read allowlisted source files in the approved repository after a session approval. Codex CLI and Claude Code are detected but disabled; inherited tool permissions have not been vetted.

## Approval-required automation

Jarvis starts a separate loopback MCP adapter for restricted Windows and browser actions. Open **Automation** to request one exact action, then review its category, arguments, risk, expiration and digest under **Security**. Approval is single-use and expires after five minutes.

Windows actions can inspect allowlisted files, list processes, start explicitly allowlisted executables with argument arrays, and stop only processes created by the current adapter session. Browser actions use an isolated Playwright context and configured host allowlist for navigation, snapshots, constrained clicks, non-sensitive text entry and screenshots.

Arbitrary shell commands, file mutation, registry/service/task changes, elevation, credential or payment entry, uploads, downloads, extensions and the normal browser profile remain blocked. Emergency Stop cancels pending automation and requests cancellation of active work. The adapter binds only to loopback and uses an ephemeral startup secret that is not persisted or sent to the browser.

## Verification

```powershell
.\.venv\Scripts\python.exe scripts\test_all.py
cd frontend
npm run build
npm test
cd ..
.\scripts\acceptance.ps1 -Base http://127.0.0.1:8767
```

Tests use isolated databases and credentials. `ASTRA_ACCEPTANCE.md` records the latest observed results and remaining limits. The Android HTTPS dashboard and task flow have been observed; a running dashboard does not by itself prove hosted-provider credentials.

## Android HTTPS

Tailscale must be installed and connected on both devices. On Skynet, private Serve is configured at `https://skynet.tail01ff2d.ts.net`, proxying to port 8767. The preview launcher sets the Tailscale node owner as the only accepted remote browser identity; Jarvis checks Serve's `Tailscale-User-Login` header for a tailnet client and issues a secure browser cookie. The HTTPS dashboard and new-task flow passed from both the laptop and an Android phone signed into the same tailnet. Do not expose the gateway through Funnel or a public reverse proxy.
