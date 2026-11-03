export type Status =
  "queued" | "running" | "cancelling" | "cancelled" | "completed" | "failed";
export interface Job {
  id: string;
  agent: string;
  prompt: string;
  status: Status;
  created: string;
  started: string | null;
  updated: string | null;
  finished: string | null;
  error: string | null;
  stream_closed: string | null;
  result: string | null;
}
export interface Agent {
  id: string;
  role: string;
  model: string;
  tool_access: boolean;
  capabilities: string[];
}
export interface Event {
  id: number;
  at: string;
  action: string;
  details: string;
}
export interface AutomationHealth {
  available: boolean;
  actions: string[];
  reason?: string;
}
export interface AutomationRequest {
  id: string;
  category: "windows" | "browser";
  action: string;
  arguments: Record<string, unknown>;
  risk: "low" | "medium" | "high";
  digest: string;
  status: string;
  created: string;
  expires: number;
  result?: unknown;
  error?: string;
}
export interface Summary {
  counts: Partial<Record<Status, number>>;
  event_id: number;
  model: string;
  concurrency: number;
  timeout_seconds: number;
  audit_retention: number;
  queue_limit: number;
  token_configured: boolean;
  tool_access: boolean;
  approved_roots: string[];
  mcp: string;
}
export interface Model {
  name: string;
  size: number;
  size_vram?: number;
}
export interface Models {
  available: boolean;
  installed: Model[];
  loaded: Model[];
  error?: string;
  unload_reason?: string;
}
export interface Telemetry {
  available: boolean;
  name?: string;
  utilization?: number;
  memory_used_mib?: number;
  memory_total_mib?: number;
  reason?: string;
  scope?: string;
}
let renewal: Promise<void> | null = null;
async function renewSession() {
  if (!renewal) {
    renewal = fetch("/control/browser-session", { method: "POST" })
      .then((r) => { if (!r.ok) throw Error("Workspace session could not be renewed"); })
      .finally(() => { renewal = null; });
  }
  await renewal;
}
async function authorizedFetch(url: string, init: RequestInit) {
  let response = await fetch(url, init);
  if (response.status === 401) {
    await renewSession();
    response = await fetch(url, init);
  }
  return response;
}
export async function api<T>(
  token: string,
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const r = await authorizedFetch("/control/" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Jarvis-Token": token, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!r.ok) {
    let detail = "Request failed";
    try {
      const data = await r.json();
      detail =
        typeof data.detail === "string"
          ? data.detail
          : "Please check your input";
    } catch {
      /* use safe fallback */
    }
    throw Error(r.status + ": " + detail);
  }
  return r.json() as Promise<T>;
}
export async function streamEvents(
  token: string,
  after: number,
  signal: AbortSignal,
  onEvent: (id: number) => void,
) {
  const r = await authorizedFetch("/control/events?after=" + after, {
    headers: { "X-Jarvis-Token": token },
    signal,
  });
  if (!r.ok || !r.body) throw Error("Live updates unavailable");
  const reader = r.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let end;
      while ((end = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        const id = block.match(/^id: (\d+)/m);
        if (id) onEvent(Number(id[1]));
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
