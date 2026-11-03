# Jarvis audit — 2026-11-03

The original service offered fixed Ollama personas, a minimal dashboard, and limited task history. The current preview adds a Windows-oriented React dashboard with focused tour and help, SQLite-backed job/result/audit state, bounded upstream responses, cooperative cancellation, session-scoped supervised file tools, temporary provider connections, and one-use approvals for local MCP tool calls.

The browser no longer asks for the admin token on the laptop. It uses an HttpOnly same-site cookie issued only for local requests. A 401 refresh path renews the cookie after a gateway restart. Server API operations still require the admin token or a valid local browser cookie. The gateway binds to loopback, rejects foreign hosts and cross-origin requests, limits request bodies and rate, and sets restrictive response headers. Provider keys remain in process memory and are not written to SQLite.

Fresh databases start without agents. The user can add Rosie, Benson, or Belvedere individually; a migration recognizes existing databases containing jobs and preserves their legacy templates. This does not yet cover arbitrary custom persona creation or model selection per agent.

MCP is currently limited to local Streamable HTTP servers. Tool discovery and an exact call request precede one-use approval. Pending requests expire after five minutes. Approval and outcomes enter the audit log. Tool behavior is determined by the connected MCP server; the current interface should be used only with trusted local servers.

Main gaps: no vetted Codex/Claude runtime adapters, no general desktop/browser/extension automation, no Android-device HTTPS round trip, and no live third-party provider credential tests. Tailscale owner-header authentication and the private HTTPS browser session work from the laptop through Serve; the Android peer has not appeared online. The validated build is running on production port 8765 after a database backup. See `ASTRA_ACCEPTANCE.md` for evidence and limits.
