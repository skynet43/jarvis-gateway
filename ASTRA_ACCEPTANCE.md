# Jarvis acceptance record — 2026-11-03

## Passed on Skynet

- Backend: `scripts/test_all.py` passed 35 isolated tests, including empty first-run setup, token/origin checks, private Tailscale owner-header checks, queues, cancellation, runtime approval, MCP discovery and one-use tool approval against a real local MCP server.
- Frontend: `npm run build` passed. The seven-test Playwright suite passed against an isolated database on port 8766, including guided-tour focus, 390 px mobile layout, WCAG 2 A/AA automated rules, saved live inference, cancellation, approved file-read runtime, help and safe output rendering, and browser-session renewal.
- Preview: port 8767 returned HTTP 200 for `/health` and `/dashboard`; the browser displayed `Workspace ready` without a token prompt. The existing preview database preserved three configured personas after migration.
- Model: Ollama on `127.0.0.1:11434` listed `tool-star-qwen:3b` from `E:\models`. `scripts/acceptance.ps1 -Base http://127.0.0.1:8767` completed and persisted a `READY` response for job `c76101dd-be1e-4e2a-bf99-680dbc018df5`.
- Production service: the prior `data/jarvis.db` was backed up as `data/jarvis-before-upgrade-20261103-013853.db`. The new build started on loopback port 8765, returned health 200, showed the three existing configured personas, and completed a persisted `READY` inference for job `1a3e585a-9355-47e7-8d5f-2806798914e9`.
- API: live preview listed 12 provider choices and exposed provider chat and MCP approval routes. MCP tool execution was validated in an isolated integration server, not through a third-party server.

## Not yet accepted

- Hosted provider authentication and billed inference were not exercised with user API keys. The catalog and adapters are present; connection to a particular account is not proven.
- Tailscale Serve is enabled at `https://skynet.tail01ff2d.ts.net` as tailnet-only HTTPS proxying to preview port 8767. `/health` and `/dashboard` returned 200. A browser opened the HTTPS URL, obtained the owner-scoped session and displayed `Workspace ready` with four saved tasks. A non-owner/missing identity is rejected in backend tests. No Android peer was online in `tailscale status`; phone access has not yet been observed.
- Desktop Commander-like full filesystem/process control, browser automation, and extension automation are not implemented in the Jarvis runtime. The existing supervised runtime is a restricted source-reading tool.
- The production port 8765 is running and passed one authenticated inference. A Windows installer/package and reboot persistence were not tested.
- Skills are local source packages only; no marketplace upload, pricing, licensing decision, or cross-agent installation was tested.

The phase is not a 100% release acceptance until these items are addressed or explicitly removed from the product scope.
