# Implementation Plan: Approval-Required Desktop and Browser Automation

## Overview

Implement a separate loopback MCP automation adapter and a Jarvis approval workflow for exact, one-use Windows and browser actions. Delivery is split into four independently testable phases: secure request state, safe Windows tools, isolated browser tools, and dashboard/operations acceptance.

## Requirements

- One immutable action and argument set per approval.
- Five-minute expiry, atomic one-use consumption, replay rejection, and complete audit history.
- Loopback-only adapter authenticated by an ephemeral startup secret.
- Configured filesystem roots, executable allowlist, adapter-owned process stopping, and bounded results.
- Dedicated Jarvis browser profile with blocked credentials, downloads, uploads, extensions, and existing-profile attachment.
- Emergency Stop handling for pending and running automation.
- No arbitrary shell, file mutation, elevation, registry, service, or scheduled-task operations.

## Architecture Changes

- `src/automation_models.py`: shared action schemas, risk labels, canonical argument serialization, and bounds.
- `src/automation_store.py`: SQLite request/event state and atomic transitions.
- `src/automation_api.py`: authenticated Jarvis endpoints and adapter client.
- `adapter/automation_adapter.py`: loopback MCP server and startup-secret validation.
- `adapter/windows_tools.py`: safe filesystem and process actions.
- `adapter/browser_tools.py`: dedicated Playwright session actions.
- `src/gateway.py`: router and lifecycle integration.
- `src/control.py`: Emergency Stop integration and summary state.
- `frontend/src/api.ts`: automation API types.
- `frontend/src/main.tsx`: Connections, Automation, Security, Tasks, and Activity UI.
- `scripts/start-automation-adapter.ps1`: secure local adapter launcher.
- `scripts/start-secure.ps1` and `scripts/start-preview.ps1`: coordinated adapter startup.
- `tests_automation.py`, `tests_automation_adapter.py`, and `frontend/tests/automation.spec.ts`: unit, integration, and E2E coverage.

## Implementation Steps

### Phase 1: Approval State — Minimum Viable

1. **Define action enums and request schemas** (File: `src/automation_models.py`)
   - Action: Add bounded Pydantic models for category, action, exact arguments, risk, and five-minute expiry.
   - Why: Reject malformed or unsupported requests before persistence.
   - Dependencies: None
   - Risk: Medium

2. **Canonicalize immutable arguments** (File: `src/automation_models.py`)
   - Action: Add deterministic JSON serialization and digest generation for the approved payload.
   - Why: Detect argument changes and bind approval to one exact request.
   - Dependencies: Step 1
   - Risk: Medium

3. **Create automation tables** (File: `src/automation_store.py`)
   - Action: Add request and event tables with status, digest, timestamps, bounded result, and sanitized error columns.
   - Why: Persist auditable state without persisting adapter secrets.
   - Dependencies: Step 1
   - Risk: Low

4. **Implement atomic state transitions** (File: `src/automation_store.py`)
   - Action: Add create, list, approve-and-consume, reject, expire, cancel, complete, and fail operations using conditional updates.
   - Why: Prevent approval replay and state races.
   - Dependencies: Steps 2-3
   - Risk: High

5. **Add request and review endpoints** (File: `src/automation_api.py`)
   - Action: Add create/list/detail/approve/reject/cancel endpoints using existing Jarvis auth.
   - Why: Expose the approval lifecycle without executing tools yet.
   - Dependencies: Step 4
   - Risk: Medium

6. **Register the router** (File: `src/gateway.py`)
   - Action: Include the automation router without changing existing routes.
   - Why: Make Phase 1 independently usable and testable.
   - Dependencies: Step 5
   - Risk: Low

7. **Test approval invariants** (File: `tests_automation.py`)
   - Action: Test schemas, expiry, immutable digests, atomic one-use approval, replay, rejection, cancellation, and audit events.
   - Why: Lock the security contract before execution exists.
   - Dependencies: Steps 1-6
   - Risk: High

8. **Phase 1 verification**
   - File: `scripts/test_all.py`
   - Action: Run the existing isolated suite with the new tests included and commit Phase 1.
   - Why: Deliver a mergeable approval-only slice.
   - Dependencies: Step 7
   - Risk: Low

### Phase 2: Safe Windows Actions — Core Experience

9. **Validate configured roots** (File: `adapter/windows_tools.py`)
   - Action: Resolve roots and targets, reject traversal and reparse-point escapes, and enforce read-only file bounds.
   - Why: Constrain filesystem visibility.
   - Dependencies: Phase 1
   - Risk: High

10. **Implement file inspection tools** (File: `adapter/windows_tools.py`)
    - Action: Add list-files, file-metadata, and bounded text-read functions with secret-name and extension filters.
    - Why: Provide useful desktop inspection without mutation.
    - Dependencies: Step 9
    - Risk: Medium

11. **Implement process listing** (File: `adapter/windows_tools.py`)
    - Action: Return a bounded, sanitized process list without command-line secrets.
    - Why: Provide safe system visibility.
    - Dependencies: Phase 1
    - Risk: Medium

12. **Implement allowlisted process start** (File: `adapter/windows_tools.py`)
    - Action: Start an exact executable path with an argument array, no shell, hidden window by default, and owned-process registration.
    - Why: Permit controlled actions without command-string injection.
    - Dependencies: Step 11
    - Risk: High

13. **Implement owned-process stop** (File: `adapter/windows_tools.py`)
    - Action: Stop only a process created by the current adapter session and remove it from the registry.
    - Why: Prevent arbitrary process termination.
    - Dependencies: Step 12
    - Risk: High

14. **Create authenticated MCP adapter** (File: `adapter/automation_adapter.py`)
    - Action: Expose only the Windows tools over loopback Streamable HTTP and reject missing or incorrect startup secrets.
    - Why: Separate privileged execution from the gateway.
    - Dependencies: Steps 9-13
    - Risk: High

15. **Add bounded adapter client** (File: `src/automation_api.py`)
    - Action: After atomic approval consumption, call the exact MCP tool once with timeouts, bounds, digest recheck, and no retry.
    - Why: Preserve one-use semantics across the process boundary.
    - Dependencies: Steps 4 and 14
    - Risk: High

16. **Add adapter health endpoint** (File: `src/automation_api.py`)
    - Action: Report reachability and supported action names without exposing the startup secret.
    - Why: Support operations and Connections UI.
    - Dependencies: Step 15
    - Risk: Low

17. **Integrate Emergency Stop** (File: `src/control.py`)
    - Action: Expire awaiting approvals, cancel queued work, and request cancellation for running automation.
    - Why: Maintain one global safety control.
    - Dependencies: Step 15
    - Risk: High

18. **Add secure launcher** (File: `scripts/start-automation-adapter.ps1`)
    - Action: Generate an ephemeral secret, validate loopback binding and roots, and launch the adapter with hidden output logs.
    - Why: Avoid persisted credentials and unsafe defaults.
    - Dependencies: Step 14
    - Risk: Medium

19. **Test Windows adapter security** (File: `tests_automation_adapter.py`)
    - Action: Test auth, traversal, junction escape, sensitive names, output bounds, disallowed executables, argument-array enforcement, ownership, replay, and adapter loss.
    - Why: Exercise the real trust boundary.
    - Dependencies: Steps 9-18
    - Risk: High

20. **Phase 2 verification**
    - File: `scripts/test_all.py`
    - Action: Run isolated tests and one approved list-process action on Skynet, then commit Phase 2.
    - Why: Deliver a mergeable Windows automation slice.
    - Dependencies: Step 19
    - Risk: Medium

### Phase 3: Isolated Browser Actions — Complete Happy Path

21. **Create dedicated browser context** (File: `adapter/browser_tools.py`)
    - Action: Launch Playwright Chromium with a Jarvis-only temporary profile and download rejection.
    - Why: Prevent access to the user's normal browser state.
    - Dependencies: Phase 2
    - Risk: High

22. **Add URL policy** (File: `adapter/browser_tools.py`)
    - Action: Permit HTTP/HTTPS only, reject credentials and dangerous schemes, and apply configured host policy.
    - Why: Block local-file and script navigation.
    - Dependencies: Step 21
    - Risk: High

23. **Implement browser session actions** (File: `adapter/browser_tools.py`)
    - Action: Add create, navigate, snapshot, and close with bounded output and in-memory session IDs.
    - Why: Establish the safe browser lifecycle.
    - Dependencies: Steps 21-22
    - Risk: Medium

24. **Implement constrained click** (File: `adapter/browser_tools.py`)
    - Action: Support accessible role/name and constrained CSS selectors while rejecting file inputs and download-triggering elements.
    - Why: Enable reviewed interaction without arbitrary evaluation.
    - Dependencies: Step 23
    - Risk: High

25. **Implement non-sensitive text entry** (File: `adapter/browser_tools.py`)
    - Action: Reject password/payment/autocomplete-sensitive fields and bound text length before filling.
    - Why: Prevent credential and payment entry.
    - Dependencies: Step 23
    - Risk: High

26. **Implement screenshots** (File: `adapter/browser_tools.py`)
    - Action: Save screenshots only under the approved Jarvis output root with generated names.
    - Why: Provide observable evidence without arbitrary writes.
    - Dependencies: Step 23
    - Risk: Medium

27. **Register browser MCP tools** (File: `adapter/automation_adapter.py`)
    - Action: Expose exact browser tools and close active contexts on shutdown.
    - Why: Complete the adapter action set.
    - Dependencies: Steps 23-26
    - Risk: Medium

28. **Test browser policy and lifecycle** (File: `tests_automation_adapter.py`)
    - Action: Test blocked schemes, credentials, password fields, uploads, downloads, selector limits, output bounds, session invalidation, and cancellation.
    - Why: Verify browser isolation and fail-closed behavior.
    - Dependencies: Step 27
    - Risk: High

29. **Phase 3 verification**
    - File: `scripts/test_all.py`
    - Action: Run isolated tests and one approved create/navigate/snapshot/close sequence against a local test page, then commit Phase 3.
    - Why: Deliver a mergeable browser automation slice.
    - Dependencies: Step 28
    - Risk: Medium

### Phase 4: Dashboard, Operations, and Acceptance

30. **Add frontend types** (File: `frontend/src/api.ts`)
    - Action: Define adapter health, action schema, request, event, and automation status types.
    - Why: Keep UI/API contracts explicit.
    - Dependencies: Phases 1-3
    - Risk: Low

31. **Add Automation request form** (File: `frontend/src/main.tsx`)
    - Action: Add category/action selection and schema-driven validated argument fields.
    - Why: Prevent free-form command entry.
    - Dependencies: Step 30
    - Risk: Medium

32. **Add Security approval cards** (File: `frontend/src/main.tsx`)
    - Action: Show exact action, arguments, risk, expiry, digest summary, and Approve once/Reject controls.
    - Why: Make informed one-use approval possible.
    - Dependencies: Step 31
    - Risk: High

33. **Add automation Tasks and Activity views** (File: `frontend/src/main.tsx`)
    - Action: Render statuses, bounded results, sanitized errors, and audit events.
    - Why: Make outcomes observable.
    - Dependencies: Step 32
    - Risk: Medium

34. **Show adapter health in Connections** (File: `frontend/src/main.tsx`)
    - Action: Display loopback adapter health, supported actions, and disabled-state guidance.
    - Why: Distinguish configured, running, and tested.
    - Dependencies: Step 30
    - Risk: Low

35. **Style automation UI** (File: `frontend/src/style.css`)
    - Action: Add responsive form, risk, expiry, status, and result styles without weakening accessibility.
    - Why: Preserve desktop and 390 px mobile usability.
    - Dependencies: Steps 31-34
    - Risk: Low

36. **Add UI E2E tests** (File: `frontend/tests/automation.spec.ts`)
    - Action: Cover creation, exact review, approval, rejection, expiry, replay, cancellation, adapter failure, Tasks, and Activity.
    - Why: Verify the complete user journey.
    - Dependencies: Steps 31-35
    - Risk: High

37. **Coordinate secure startup** (File: `scripts/start-secure.ps1`)
    - Action: Start or validate the adapter before production gateway startup without silently replacing existing listeners.
    - Why: Make production launch repeatable.
    - Dependencies: Step 18
    - Risk: Medium

38. **Coordinate preview startup** (File: `scripts/start-preview.ps1`)
    - Action: Start an isolated adapter configuration for preview and acceptance.
    - Why: Keep preview data and processes separate.
    - Dependencies: Step 18
    - Risk: Medium

39. **Document supported automation** (File: `README.md`)
    - Action: Document setup, approval flow, allowed actions, blocked actions, Emergency Stop, and limitations.
    - Why: Set accurate operator expectations.
    - Dependencies: Steps 30-38
    - Risk: Low

40. **Update acceptance record** (File: `ASTRA_ACCEPTANCE.md`)
    - Action: Record observed Windows and browser actions, test counts, service health, and remaining restrictions.
    - Why: Separate verified behavior from configured capability.
    - Dependencies: Step 41
    - Risk: Low

41. **Run final acceptance** (File: `scripts/test_all.py`)
    - Action: Run backend tests, frontend build, Playwright suites, secret scan, diff check, production/preview health, one Windows action, and one browser action.
    - Why: Verify the release boundary before claiming completion.
    - Dependencies: Steps 30-39
    - Risk: High

42. **Phase 4 delivery**
    - File: `docs/plans/2026-11-03-approval-required-automation.md`
    - Action: Commit the final implementation and acceptance evidence, push main, and verify local and remote commit equality.
    - Why: Finish with a clean, reproducible repository state.
    - Dependencies: Steps 40-41
    - Risk: Low

## Testing Strategy

- Unit: `tests_automation.py` covers models, canonical digests, state transitions, expiry, cancellation, replay, and audit records.
- Integration: `tests_automation_adapter.py` launches the real loopback MCP adapter with temporary roots, executables, browser profiles, and output directories.
- Existing regression: `scripts/test_all.py` continues to discover all `tests_*.py` files.
- E2E: `frontend/tests/automation.spec.ts` verifies the approval UI and actual safe local adapter actions.
- Security: targeted cases cover path/reparse escape, command injection, unauthorized process stopping, blocked URL schemes, credential fields, upload/download, oversized data, secret leakage, and consumed-approval replay.
- Manual acceptance: approve one safe Windows process-list action and one local-page browser sequence on Skynet.

## Success Criteria

- [ ] Adapter listens only on loopback and rejects missing/incorrect startup secrets.
- [ ] Every executable action requires an unexpired, exact, single-use approval.
- [ ] Replay and changed arguments fail closed.
- [ ] Windows actions remain inside configured roots and process ownership rules.
- [ ] Browser actions use only the dedicated Jarvis profile and reject sensitive operations.
- [ ] Emergency Stop covers automation requests and executions.
- [ ] Results and errors are bounded, sanitized, persisted, and audited.
- [ ] Backend, integration, frontend build, E2E, and secret scans pass.
- [ ] One approved Windows action and one approved browser action are observed on Skynet.
- [ ] Production and preview remain healthy with a clean, pushed repository.
