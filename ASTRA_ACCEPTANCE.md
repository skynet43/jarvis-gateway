# Jarvis acceptance record — 2026-11-03

## Passed on Skynet

- Backend: `scripts/test_all.py` passed 47 isolated tests, including empty first-run setup, token/origin checks, private Tailscale owner-header checks, queues, cancellation, runtime approval, MCP discovery, one-use tool approval, exact automation approvals, adapter authentication, and real restricted Windows/browser integration.
- Frontend: `npm run build` passed. The eight-test Playwright suite passed against an isolated database on port 8766, including guided-tour focus, 390 px mobile layout, WCAG 2 A/AA automated rules, saved live inference, race-safe queued/running cancellation, approved file-read runtime, exact one-use automation approval, help and safe output rendering, and browser-session renewal.
- Preview: port 8767 returned HTTP 200 for `/health` and `/dashboard`; the browser displayed `Workspace ready` without a token prompt. The existing preview database preserved three configured personas after migration.
- Model: Ollama on `127.0.0.1:11434` listed `tool-star-qwen:3b` from `E:\models`. `scripts/acceptance.ps1 -Base http://127.0.0.1:8767` completed and persisted a `READY` response for job `c76101dd-be1e-4e2a-bf99-680dbc018df5`.
- Production service: the prior `data/jarvis.db` was backed up as `data/jarvis-before-upgrade-20261103-013853.db`. The new build started on loopback port 8765, returned health 200, showed the three existing configured personas, and completed a persisted `READY` inference for job `1a3e585a-9355-47e7-8d5f-2806798914e9`.
- API: live preview listed 12 provider choices and exposed provider chat and MCP approval routes. MCP tool execution was validated in an isolated integration server, not through a third-party server.
- Android: Tailscale Serve at `https://skynet.tail01ff2d.ts.net` provided the owner-scoped HTTPS dashboard to an Android phone. The phone displayed `Workspace ready` and successfully submitted and ran a new task. A non-owner/missing identity is rejected in backend tests.

## Not yet accepted

- Hosted provider authentication and billed inference were not exercised with user API keys. The catalog and adapters are present; connection to a particular account is not proven.
- Approval-required automation is implemented for allowlisted Windows file/process operations and isolated-browser create/navigate/snapshot/click/fill/screenshot operations. Arbitrary desktop UI control, unrestricted filesystem/shell access, browser-extension control, credential/password entry, uploads/downloads, and normal browser-profile access remain outside the accepted scope.
- The production port 8765 is running and passed one authenticated inference. A Windows installer/package and reboot persistence were not tested.
- Skills are local source packages only; no marketplace upload, pricing, licensing decision, or cross-agent installation was tested.

The phase is not a 100% release acceptance until these items are addressed or explicitly removed from the product scope.
