---
name: jarvis-acceptance
description: Validate Jarvis Gateway changes with isolated backend and browser tests, real Ollama inference, approval-bound tool execution, and precise cancellation evidence.
---
# Jarvis acceptance

Use for release or regression verification of an existing Jarvis repository. Preserve the live database and running instance.

## Reproducible checks

- Inspect README, package scripts and tests before running them. Check that tests use temporary databases and test-only credentials.
- Run the repository virtual-environment Python with scripts/test_all.py. Record the original regression count separately from added tests.
- In frontend, run npm ci, npm run typecheck, npm run lint and npm run build. Run npm test for the isolated Chromium server on loopback port 8766; ensure this port is free first. Never reuse an unknown listener.
- The browser suite should exercise the focused tour, automatic local session renewal, desktop/mobile screens, accessible controls, persisted real output, queued and running cancellation, runtime approval and an actual successful tool call. A mocked XSS fixture is useful but is not live inference proof. Backend tests should verify a fresh empty agent list and an individually selected template.
- Inspect generated screenshots rather than calling successful screenshot capture visual acceptance. Tokens must be absent from screenshots and bundles.
- scripts/measure_cancellation.py uses JARVIS_ADMIN_TOKEN and optional JARVIS_BASE_URL. Run it only against an authorized review instance with no unrelated tasks. Record all trials, including invalid trials where the task finished before cancellation. Keep baseline/during/after GPU and VRAM samples distinct.
- Check authenticated API compatibility, startup/shutdown, repository exclusions, dependency findings and current listeners.

## Interpretation

A green build is not a running app. A loaded page is not feature acceptance. A completed runtime session is not tool execution unless its audit contains a successful tool call. Request closure is not proof of GPU inference stop, and low GPU utilization is not proof of VRAM release.

Report exact commands, counts, failures and limitations in ASTRA_ACCEPTANCE.md. Preserve failures and fixes in the audit trail rather than silently skipping cases. If runtime acceptance fails, do not label the release ready or distribute an installer.

Packaging skill folders does not authorize marketplace publication, account changes, licensing claims or charging buyers.
