# Approval-Required Desktop and Browser Automation Design

Date: 2026-11-03
Status: Approved design; implementation not started

## Goal

Add Windows desktop/file/process automation and browser automation to Jarvis while preserving explicit human control. Every executable action must be reviewed as an exact, one-use request before it runs.

## Architecture

The data flow is:

1. The Jarvis dashboard creates a validated automation request.
2. The request appears in Security with its exact action, target, arguments, risk label, and expiration.
3. The user approves once or rejects it.
4. After approval, Jarvis sends the exact request to a loopback-only automation MCP adapter.
5. The adapter validates the request again, executes one allowed action, and returns a bounded result.
6. Jarvis records request, decision, execution, outcome, and sanitized errors in the audit log.

The adapter is a separate local process so privileged automation does not run inside the web gateway. It binds only to `127.0.0.1` and authenticates gateway calls with a random startup secret that is never sent to the browser or persisted.

## Initial Action Set

Windows actions:

- List files within configured roots.
- Read file metadata and bounded text content within configured roots.
- List processes.
- Start an explicitly allowlisted executable using a path plus argument array.
- Stop a process that was started through the adapter during the current adapter session.

Browser actions:

- Create and close a browser session using a dedicated Jarvis profile.
- Navigate to an HTTP or HTTPS URL allowed by URL policy.
- Read page title, URL, and bounded accessibility/text snapshot.
- Click an element selected by an accessible role/name or a constrained CSS selector.
- Enter non-sensitive text into a non-password field.
- Capture a screenshot to an approved Jarvis output directory.

## Explicitly Blocked

The first release does not permit:

- Arbitrary shell command strings or script evaluation.
- File deletion, moving, writing, or uploads.
- Registry, service, scheduled-task, firewall, account, or privilege changes.
- Elevation or UAC interaction.
- Credential, password, payment, recovery-code, or secret entry.
- Browser downloads, extension installation/control, or use of the user's normal browser profile.
- Actions outside configured filesystem roots.
- Reuse, bulk approval, standing approval, or “always allow.”

## Approval and Execution Rules

- One approval authorizes exactly one immutable action and argument set.
- Requests expire five minutes after creation.
- Approval tokens are single-use and atomically consumed before execution.
- Replayed, changed, expired, rejected, or already-used requests fail closed.
- Inputs are validated both in Jarvis and independently in the adapter.
- Filesystem targets are resolved before comparison with configured roots; path traversal and symlink/junction escapes are rejected.
- Executables must match an explicit allowlist and receive arguments as an array.
- Stop-process is limited to adapter-owned processes from the current adapter session.
- Browser automation uses a new dedicated profile and cannot attach to existing browser sessions.
- Results and errors are size-bounded and sanitized before storage.
- Emergency Stop rejects pending requests and requests cancellation of running automation.

## Dashboard

Connections displays adapter health and supported actions.

Automation lets the user choose Windows or Browser, select an allowed action, and enter schema-validated arguments.

Security displays every awaiting request with its exact action, target, arguments, risk label, and expiration, plus Approve once and Reject controls.

Tasks displays queued, running, completed, failed, cancelled, and expired automation executions.

Activity records requester, approval decision, execution timestamps, sanitized outcome, and errors.

## State

Jarvis persists request metadata, status, timestamps, action, sanitized arguments, bounded result, and audit events in SQLite. It does not persist the adapter secret, browser profile secrets, credentials, or sensitive page input.

The adapter keeps its owned-process registry and browser sessions in memory. They are invalid after adapter restart.

## Failure Handling

Adapter unavailability leaves requests failed without fallback execution. Validation failures do not create executable approvals. A lost connection cannot cause automatic retry of a consumed approval. Cancellation is best effort for an already-running operating-system or browser action and is recorded accurately.

## Acceptance Criteria

- Unit tests cover schemas, expiration, immutable arguments, one-use consumption, replay prevention, and status transitions.
- Security tests cover path traversal, symlink/junction escape, disallowed executables, shell metacharacters, blocked URLs, password fields, downloads, uploads, and oversized results.
- Isolated integration tests exercise the real loopback adapter without touching user files or browser profiles.
- Browser UI tests cover request creation, exact review, approval, rejection, expiration, cancellation, and Activity records.
- Emergency Stop covers pending and running automation.
- Secret scanning and existing backend/frontend regression suites pass.
- One real approved safe Windows action and one real approved safe browser action pass on Skynet.
- Documentation states the supported action set and remaining restrictions.

## Out of Scope

Extension automation, arbitrary desktop clicking, OCR-driven control, unrestricted shell access, file mutation, credential entry, privilege elevation, remote adapter exposure, persistent approvals, and marketplace publication are separate future decisions.
