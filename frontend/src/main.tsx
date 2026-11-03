import React, { useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  Bot,
  ListTodo,
  Activity,
  Boxes,
  Plug,
  Shield,
  Settings,
  HelpCircle,
  ArrowUpRight,
  Plus,
  Square,
  RefreshCw,
  ChevronRight,
  X,
  Radio,
  Lock,
  Check,
  Search,
  Play,
  Download,
  Command,
  Monitor,
  Smartphone,
} from "lucide-react";
import {
  api,
  approveAutomation,
  streamEvents,
  type Job,
  type Agent,
  type Event,
  type Summary,
  type Models,
  type Telemetry,
  type AutomationHealth,
  type AutomationRequest,
} from "./api";
import "./style.css";
const pages = [
  "Overview",
  "Agents",
  "Tasks",
  "Activity",
  "Models",
  "Connections",
  "Automation",
  "Security",
  "Settings",
] as const;
type Page = (typeof pages)[number];
const icons = [
  LayoutDashboard,
  Bot,
  ListTodo,
  Activity,
  Boxes,
  Plug,
  Command,
  Shield,
  Settings,
];
const names: Record<string, string> = {
  rosie: "Rosie",
  benson: "Benson",
  "mr-belvedere": "Mr. Belvedere",
};
const date = (s: string | null) => (s ? new Date(s).toLocaleString() : "—");
function Modal({
  title,
  children,
  onClose,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.showModal();
    return () => {
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={className}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-label={title}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon" aria-label="Close" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
const steps = [
  {
    target: "brand",
    title: "Your command center",
    text: "One place to supervise tasks and runtimes. Start here for a clear view of what is running and what needs you.",
  },
  {
    target: "auth",
    title: "Ready when you are",
    text: "Your workspace connects automatically on this laptop. This bar shows connection health and the most recent update.",
  },
  {
    target: "navigation",
    title: "Find your workspace",
    text: "Move between tasks, agents, activity and security. Keyboard Tab moves through controls; Enter activates them.",
  },
  {
    target: "new-task",
    title: "Give a task a clear goal",
    text: "Choose a persona for text help, or an approved runtime for a supervised session. You can review outputs and stop work from Tasks.",
  },
  {
    target: "stop",
    title: "Stay in control",
    text: "Stop requests cancellation of gateway tasks. It does not shut down Windows or unload models. A running task stays cancelling until its request closes.",
  },
  {
    target: "help",
    title: "Help is always here",
    text: "Open the guide for instant app instructions, replay this tour, or ask Rosie for AI help. You are ready to begin.",
  },
];
const helpTopics = [
  [
    "How do I start?",
    "Choose New task, pick a persona, describe your goal, and queue it. Open Tasks to follow the result.",
  ],
  [
    "What is a persona?",
    "Rosie, Benson and Mr. Belvedere are named Ollama prompts. They generate text and have no shell or file access. Connected runtimes have separate permissions and approvals.",
  ],
  [
    "How do I stop a task?",
    "Select a task and choose Cancel. Queued tasks cancel immediately. Running tasks move through cancelling until the request stream closes. That does not prove GPU inference has stopped or that a model has unloaded.",
  ],
  [
    "How do runtime approvals work?",
    "Create a runtime request in Connections. Review the exact prompt, workspace and permission scope in Security before approving it. Only configured runtimes and approved roots can run.",
  ],
  [
    "Can I use my Android phone?",
    "Use your laptop’s private Tailscale HTTPS address while Tailscale is connected on both devices. The laptop must stay awake and online. The Android dashboard and task flow have been verified.",
  ],
  [
    "Why is my connection offline?",
    "Check that the gateway and Ollama are running. Refresh the page if the local connection needs to be restored. Live events reconnect automatically, with polling as a fallback.",
  ],
  [
    "Where are my results?",
    "Open Tasks, select a completed task, and read its saved output. Results are stored in the gateway database. Search and status filters help you find older tasks.",
  ],
];
interface Runtime {
  id: string;
  name: string;
  available: boolean;
  permissions: string;
  roots: string[];
}
interface Session {
  id: string;
  runtime: string;
  prompt: string;
  root: string;
  status: string;
  created: string;
  result?: string;
  error?: string;
}
function App() {
  type Provider = {id:string;name:string;protocol:string;default_endpoint:string|null;connected:boolean};
  const [page, setPage] = useState<Page>("Overview"),
    [token, setToken] = useState(""),
    [connected, setConnected] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]),
    [agents, setAgents] = useState<Agent[]>([]),
    [events, setEvents] = useState<Event[]>([]),
    [summary, setSummary] = useState<Summary | null>(null),
    [models, setModels] = useState<Models | null>(null),
    [gpu, setGpu] = useState<Telemetry | null>(null);
  const [runtimes, setRuntimes] = useState<Runtime[]>([]),
    [sessions, setSessions] = useState<Session[]>([]);
  const [automationHealth,setAutomationHealth]=useState<AutomationHealth | null>(null),
    [automationRequests,setAutomationRequests]=useState<AutomationRequest[]>([]),
    [automationCategory,setAutomationCategory]=useState<"windows"|"browser">("windows"),
    [automationAction,setAutomationAction]=useState("list_processes"),
    [automationArguments,setAutomationArguments]=useState("{}");
  const [providers,setProviders]=useState<Provider[]>([]),
    [providerId,setProviderId]=useState("ollama"),
    [providerEndpoint,setProviderEndpoint]=useState(""),
    [providerKey,setProviderKey]=useState(""),
    [providerModels,setProviderModels]=useState<string[]>([]),
    [providerModel,setProviderModel]=useState(""),
    [providerPrompt,setProviderPrompt]=useState(""),
    [providerReply,setProviderReply]=useState("");
  type McpServer={id:string;name:string;url:string;tools:{name:string;description:string}[]};
  type McpRequest={id:string;server:string;tool:string;arguments:Record<string,unknown>};
  const [mcpServers,setMcpServers]=useState<McpServer[]>([]),
    [mcpRequests,setMcpRequests]=useState<McpRequest[]>([]),
    [mcpName,setMcpName]=useState(""),[mcpUrl,setMcpUrl]=useState(""),
    [mcpServerId,setMcpServerId]=useState(""),[mcpTool,setMcpTool]=useState(""),
    [mcpArguments,setMcpArguments]=useState("{}");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [live, setLive] = useState(false),
    [lastSync, setLastSync] = useState(""),
    [clock, setClock] = useState(new Date());
  const [compose, setCompose] = useState(false),
    [agent, setAgent] = useState("rosie"),
    [prompt, setPrompt] = useState(""),
    [selected, setSelected] = useState<Job | null>(null),
    [help, setHelp] = useState(false),
    [helpQuery, setHelpQuery] = useState("");
  const [filter, setFilter] = useState(""),
    [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0),
    [confirm, setConfirm] = useState(false);
  const [tour, setTour] = useState<number | null>(() =>
      localStorage.getItem("jarvis-tour-done")
        ? null
        : Number(localStorage.getItem("jarvis-tour-step") || 0),
    ),
    [refresh, setRefresh] = useState(() =>
      Number(localStorage.getItem("jarvis-refresh") || 5),
    ),
    [contrast, setContrast] = useState(
      () => localStorage.getItem("jarvis-contrast") === "true",
    );
  const [runtimePrompt, setRuntimePrompt] = useState(""),
    [runtimeRoot, setRuntimeRoot] = useState(""),
    [runtimeId, setRuntimeId] = useState("ollama-tools");
  const cursor = useRef(0),
    loading = useRef(false),
    tourHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    let cancelled = false;
    async function connectWorkspace() {
      try {
        let response = await fetch("/control/browser-session", {method: "POST"});
        let sessionToken = "private-owner-session";
        if (response.status === 401) {
          const entered = window.prompt("Enter the Jarvis admin token to open this local workspace.");
          if (!entered) throw new Error("Admin token confirmation is required.");
          response = await fetch("/control/browser-session", {
            method: "POST",
            headers: {"X-Jarvis-Token": entered},
          });
          sessionToken = entered;
        }
        if (!response.ok) throw new Error("Workspace connection is unavailable.");
        if (!cancelled) {setToken(sessionToken); setError("");}
      } catch (e) {
        if (!cancelled) {setError(String(e));}
      }
    }
    void connectWorkspace();
    return () => {cancelled=true;};
  }, []);
  useEffect(() => {
    if (!token) return;
    void api<Provider[]>(token,"providers").then(setProviders).catch(() => {});
    void api<McpServer[]>(token,"mcp/servers").then(setMcpServers).catch(() => {});
    void api<McpRequest[]>(token,"mcp/requests").then(setMcpRequests).catch(() => {});
  }, [token]);
  const load = useCallback(
    async (key = token) => {
      if (!key || loading.current) return;
      loading.current = true;
      try {
        const [j, a, e, s, m, g, r, se, ah, ar] = await Promise.all([
          api<Job[]>(
            key,
            "jobs?limit=50&offset=" +
              offset +
              "&status=" +
              encodeURIComponent(filter) +
              "&q=" +
              encodeURIComponent(search),
          ),
          api<Agent[]>(key, "agents"),
          api<Event[]>(key, "audit"),
          api<Summary>(key, "summary"),
          api<Models>(key, "models"),
          api<Telemetry>(key, "telemetry"),
          api<Runtime[]>(key, "runtimes"),
          api<Session[]>(key, "sessions"),
          api<AutomationHealth>(key, "automation/health"),
          api<AutomationRequest[]>(key, "automation/requests"),
        ]);
        setJobs(j);
        setAgents(a);
        setEvents(e);
        setSummary(s);
        setModels(m);
        setGpu(g);
        setRuntimes(r);
        setSessions(se);
        setAutomationHealth(ah);
        setAutomationRequests(ar);
        setConnected(true);
        setLastSync(new Date().toLocaleTimeString());
        setError("");
      } catch (e) {
        setError(String(e));
        setConnected(false);
      } finally {
        loading.current = false;
      }
    },
    [token, offset, filter, search],
  );
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), refresh * 1000);
    return () => clearInterval(id);
  }, [load, refresh]);
  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    if (!token) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const run = async () => {
      try {
        setLive(true);
        await streamEvents(token, cursor.current, abort.signal, (id) => {
          cursor.current = id;
          void load();
        });
      } catch {
        /* polling remains active */
      } finally {
        setLive(false);
        if (!abort.signal.aborted) timer = setTimeout(() => void run(), 3000);
      }
    };
    void run();
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [token, load]);
  useEffect(() => {
    document.documentElement.dataset.contrast = String(contrast);
    localStorage.setItem("jarvis-contrast", String(contrast));
  }, [contrast]);
  useEffect(() => {
    if (tour === null) return;
    localStorage.setItem("jarvis-tour-step", String(tour));
    const el = document.getElementById(steps[tour].target);
    el?.classList.add("tour-focus");
    el?.scrollIntoView({ block: "nearest", behavior: "instant" });
    tourHeading.current?.focus();
    return () => el?.classList.remove("tour-focus");
  }, [tour]);
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  function newTask(a = "rosie", text = "") {
    setAgent(a);
    setPrompt(text);
    setCompose(true);
  }
  function exportAudit() {
    const blob = new Blob([JSON.stringify(events, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "jarvis-audit.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  const counts = summary?.counts || {},
    active = (counts.running || 0) + (counts.cancelling || 0),
    pending = sessions.filter((s) => s.status === "awaiting_approval"),
    automationPending = automationRequests.filter((r) => r.status === "awaiting_approval");
  const taskList = (
    <>
      <div className="tools">
        <label className="search">
          <Search size={17} />
          <input
            aria-label="Search tasks"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <select
          aria-label="Filter task status"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All statuses</option>
          {[
            "queued",
            "running",
            "cancelling",
            "cancelled",
            "completed",
            "failed",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div className="task-list">
        {jobs.length ? (
          jobs.map((j) => (
            <button
              className="task-row"
              key={j.id}
              onClick={() => setSelected(j)}
            >
              <span className={"status-dot " + j.status} />
              <span className="grow">
                <strong>{j.prompt}</strong>
                <small>
                  {names[j.agent] || j.agent} · {date(j.created)}
                </small>
              </span>
              <span className={"badge " + j.status}>{j.status}</span>
              <ChevronRight size={16} />
            </button>
          ))
        ) : (
          <div className="empty">
            <ListTodo />
            <h3>
              {connected
                ? "A clear queue. A fresh start."
                : "Connecting to your workspace"}
            </h3>
            <p>
              {connected
                ? "Create a task and its progress will appear here."
                : "Your saved tasks will appear as soon as the gateway responds."}
            </p>
          </div>
        )}
      </div>
      <div className="pagination">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous
        </button>
        <small>
          Showing {jobs.length ? offset + 1 : 0}–{offset + jobs.length}
        </small>
        <button
          disabled={jobs.length < 50}
          onClick={() => setOffset(offset + 50)}
        >
          Next
        </button>
      </div>
    </>
  );
  return (
    <div className="app">
      <aside>
        <div id="brand" className="brand">
          <div className="brand-mark">
            <Command />
          </div>
          <div>
            JARVIS<small>SKYNET COMMAND CENTER</small>
          </div>
        </div>
        <div className="workspace">
          <Monitor size={16} />
          <div>
            Windows workspace<small>Local control · private by design</small>
          </div>
        </div>
        <nav id="navigation" aria-label="Main navigation">
          {pages.map((p, i) => {
            const Icon = icons[i];
            return (
              <button
                key={p}
                className={page === p ? "active" : ""}
                aria-current={page === p ? "page" : undefined}
                onClick={() => setPage(p)}
              >
                <Icon size={18} />
                {p}
                {p === "Security" && pending.length + automationPending.length > 0 && (
                  <span className="nav-count">{pending.length + automationPending.length}</span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="aside-bottom">
          <button
            id="help"
            className="help-button"
            onClick={() => setHelp(true)}
          >
            <HelpCircle size={19} />
            <span>
              Need a hand?<small>Meet your command center guide</small>
            </span>
            <ChevronRight size={15} />
          </button>
          <div className="version">
            <span className="status-dot" />
            <span>Jarvis / 02</span>
            <span>LOCAL FIRST</span>
          </div>
        </div>
      </aside>
      <div className="main">
        <header>
          <div className="breadcrumbs">
            Workspace <ChevronRight size={13} />
            <strong>{page}</strong>
          </div>
          <button
            className="icon mobile-help"
            aria-label="Open help"
            onClick={() => setHelp(true)}
          >
            <HelpCircle size={18} />
          </button>
          <div className="top-status">
            <span
              className={"status-dot " + (connected ? "completed" : "failed")}
            />
            {connected ? "Gateway connected" : "Not connected"}
            <span className="divider" />
            <time>
              {clock.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </time>
          </div>
          <button
            id="stop"
            className="danger subtle"
            disabled={!connected || busy}
            onClick={() => setConfirm(true)}
          >
            <Square size={13} /> Stop tasks
          </button>
        </header>
        <main>
          <section className="page-title">
            <div>
              <div className="eyebrow">YOUR WORK. UNDER CONTROL.</div>
              <h1>{page === "Overview" ? "Mission control" : page}</h1>
              <p>
                {page === "Overview"
                  ? "A clear view of your agents, tasks, and local intelligence."
                  : (
                      {
                        Agents: "Know exactly who can do what.",
                        Tasks: "From a clear goal to a saved result.",
                        Activity: "A traceable record of what happened.",
                        Models: "Local intelligence, real availability.",
                        Connections: "Connect runtimes. Keep control.",
                        Automation: "Request one exact action at a time.",
                        Security: "Explicit permissions. Visible decisions.",
                        Settings: "Make the workspace yours.",
                      } as Record<string, string>
                    )[page]}
              </p>
            </div>
            <button
              id="new-task"
              className="primary"
              disabled={!connected||agents.length===0}
              onClick={() => newTask()}
            >
              <Plus size={17} /> New task
            </button>
          </section>
          <section id="auth" className="auth-strip" aria-live="polite">
            <span className="secure"><Radio size={15}/>{connected ? "Workspace ready" : "Connecting to workspace…"}</span>
            <span className="muted">{connected ? (live ? "Live updates" : "Automatic refresh") : "Opening your local workspace"}{lastSync ? " · Updated " + lastSync : ""}</span>
            <button className="text-button" onClick={() => void load()} aria-label="Refresh"><RefreshCw size={16}/></button>
          </section>
          {error && (
            <div role="alert" className="error">
              <strong>Something needs attention</strong>
              <span>{error}</span>
              <button onClick={() => void load()}>Try again</button>
            </div>
          )}
          {page === "Overview" && (
            <>
              <div className="stats">
                {[
                  ["Queued", counts.queued, "Waiting their turn"],
                  ["Running", active, "Currently in progress"],
                  ["Completed", counts.completed, "Results ready to review"],
                  ["Failed", counts.failed, "May need your attention"],
                ].map(([label, note, sub]) => (
                  <button
                    className="stat"
                    key={String(label)}
                    onClick={() => {
                      setFilter(String(label).toLowerCase());
                      setPage("Tasks");
                    }}
                  >
                    <span>{label}</span>
                    <strong>{connected ? note || 0 : "—"}</strong>
                    <small>{sub}</small>
                  </button>
                ))}
              </div>
              <div className="overview-grid">
                <section className="panel mission">
                  {connected&&agents.length===0&&<button className="primary" onClick={()=>setPage("Agents")}>Set up your first agent</button>}
                  <div className="section-head">
                    <div>
                      <span className="eyebrow">LOCAL INTELLIGENCE</span>
                      <h2>Your team, in focus</h2>
                    </div>
                    <span className="badge">{agents.length} personas</span>
                  </div>
                  <div className="orbit">
                    <div className={"core " + (active ? "working" : "")}>
                      <Command size={34} />
                      <strong>JARVIS</strong>
                      <small>
                        {connected
                          ? active
                            ? "Processing tasks"
                            : "Ready when you are"
                          : "Awaiting connection"}
                      </small>
                    </div>
                    {agents.map((entry, i) => (
                      <button
                        key={entry.id}
                        className={"satellite s" + i}
                        disabled={!connected}
                        onClick={() => {
                          setAgent(entry.id);
                          setPage("Agents");
                        }}
                      >
                        <Bot size={20} />
                        <span>{names[entry.id] || entry.id}</span>
                        <small>Text persona</small>
                      </button>
                    ))}
                  </div>
                  <div className="mission-footer">
                    <span>
                      <span
                        className={
                          "status-dot " +
                          (models?.available ? "completed" : "failed")
                        }
                      />
                      {models?.available
                        ? "Ollama available"
                        : "Ollama not verified"}
                    </span>
                    <span>{summary?.model || "Model not loaded"}</span>
                  </div>
                </section>
                <section className="panel">
                  <div className="section-head">
                    <h2>System pulse</h2>
                    <Radio size={18} />
                  </div>
                  <div className="pulse-item">
                    <span>Inference engine</span>
                    <strong>
                      {models?.available
                        ? "Online"
                        : connected
                          ? "Unavailable"
                          : "Not checked"}
                    </strong>
                  </div>
                  <div className="pulse-item">
                    <span>Loaded models</span>
                    <strong>{models?.loaded.length ?? "—"}</strong>
                  </div>
                  <div className="pulse-item">
                    <span>Connected runtimes</span>
                    <strong>
                      {runtimes.filter((r) => r.available).length}
                    </strong>
                  </div>
                  <div className="gpu">
                    <span className="eyebrow">HARDWARE TELEMETRY</span>
                    <h3>{gpu?.available ? gpu.name : "No telemetry yet"}</h3>
                    {gpu?.available ? (
                      <>
                        <div className="gpu-number">
                          {gpu.utilization}
                          <small>% GPU</small>
                        </div>
                        <meter
                          min={0}
                          max={100}
                          value={gpu.utilization}
                          aria-label="GPU utilization"
                        />
                        <p>
                          {gpu.memory_used_mib} / {gpu.memory_total_mib} MiB
                          VRAM
                        </p>
                        <small>Whole GPU · includes other applications</small>
                      </>
                    ) : (
                      <p>
                        Real readings appear when NVIDIA telemetry is available.
                      </p>
                    )}
                  </div>
                </section>
              </div>
              <section className="panel">
                <div className="section-head">
                  <h2>Recent tasks</h2>
                  <button
                    className="text-button"
                    onClick={() => setPage("Tasks")}
                  >
                    View all <ArrowUpRight size={15} />
                  </button>
                </div>
                {taskList}
              </section>
            </>
          )}
          {page === "Tasks" && <section className="panel">{taskList}</section>}
          {page === "Agents" && (
            <>
              {agents.length<3&&<section className="panel"><h2>Set up your agents</h2><p>Add only the assistants you want.</p>{(["rosie","benson","mr-belvedere"] as const).filter((id)=>!agents.some((a)=>a.id===id)).map((id)=><button key={id} onClick={()=>void action(async()=>{setAgents(await api<Agent[]>(token,"agents/setup",{templates:[id]}));})}>Add {names[id]}</button>)}<p className="muted">You can also connect a model provider and MCP tools in Connections.</p></section>}
              <div className="notice">
                <Bot size={20} />
                <p>
                  Personas generate text through Ollama. Runtime sessions are
                  separate, permission-scoped processes managed in Connections.
                </p>
              </div>
              <div className="cards">
                {agents.map((a, i) => (
                  <section className="panel agent-card" key={a.id}>
                    <div className={"avatar a" + i}>
                      <Bot size={30} />
                    </div>
                    <h2>{names[a.id]}</h2>
                    <span className="eyebrow">{a.role}</span>
                    <p>
                      {i === 0
                        ? "A thoughtful partner for questions, drafts and explanations."
                        : i === 1
                          ? "Turn a broad goal into clear priorities and next steps."
                          : "Review a problem and explain a careful maintenance plan."}
                    </p>
                    <div className="capability">
                      <Check size={14} /> Text inference <Lock size={13} /> No
                      tool access
                    </div>
                    <small>{a.model}</small>
                    <button onClick={() => newTask(a.id)}>
                      Give {names[a.id]} a task <ArrowUpRight size={16} />
                    </button>
                  </section>
                ))}
              </div>
            </>
          )}
          {page === "Activity" && (
            <section className="panel">
              <div className="section-head">
                <h2>Audit trail</h2>
                <button disabled={!events.length} onClick={exportAudit}>
                  <Download size={15} /> Export visible events
                </button>
              </div>
              <div className="timeline">
                {events.map((e) => (
                  <article key={e.id}>
                    <span className="timeline-dot" />
                    <div>
                      <strong>{e.action.replaceAll(".", " / ")}</strong>
                      <small>
                        Event #{e.id} · {date(e.at)}
                      </small>
                      <code>{e.details}</code>
                    </div>
                  </article>
                ))}
                {!events.length && (
                  <div className="empty">
                    Activity will appear after you connect and use the gateway.
                  </div>
                )}
              </div>
            </section>
          )}
          {page === "Models" && (
            <>
              <div className="notice">
                <Lock size={20} />
                <p>
                  {models?.unload_reason ||
                    "Model unload stays disabled unless exclusive session ownership can be established."}
                </p>
              </div>
              <div className="cards">
                {models?.installed.map((m) => (
                  <section className="panel" key={m.name}>
                    <Boxes className="accent" />
                    <h2>{m.name}</h2>
                    <span className="badge">
                      {models.loaded.some((l) => l.name === m.name)
                        ? "Loaded"
                        : "Installed"}
                    </span>
                    <p>{(m.size / 1073741824).toFixed(2)} GiB on disk</p>
                    <small>
                      {m.name === summary?.model
                        ? "Current persona model"
                        : "Available in Ollama"}
                    </small>
                  </section>
                ))}
              </div>
              {!models?.installed.length && (
                <section className="panel empty">
                  No installed models reported.
                </section>
              )}
            </>
          )}
          {page === "Connections" && (
            <>
              <section className="panel"><Command className="accent"/><h2>Automation adapter</h2><span className={"badge "+(automationHealth?.available?"completed":"failed")}>{automationHealth?.available?"Connected · approval required":"Unavailable"}</span><p>{automationHealth?.available?automationHealth.actions.length+" safe actions available":automationHealth?.reason||"Connect to verify"}</p><button onClick={()=>setPage("Automation")} disabled={!automationHealth?.available}>Request an action</button></section>
              <section className="panel">
                <h2>MCP tools</h2>
                <p className="muted">Connect a local MCP HTTP server, inspect its tools, then approve each call.</p>
                <form className="stack" onSubmit={(e)=>{e.preventDefault();void action(async()=>{
                  await api(token,"mcp/servers",{name:mcpName,url:mcpUrl});
                  setMcpServers(await api<McpServer[]>(token,"mcp/servers"));setMcpName("");setMcpUrl("");
                });}}>
                  <label>Server name<input value={mcpName} onChange={(e)=>setMcpName(e.target.value)} required/></label>
                  <label>Local MCP URL<input value={mcpUrl} onChange={(e)=>setMcpUrl(e.target.value)} placeholder="http://127.0.0.1:8000/mcp" required/></label>
                  <button className="primary" disabled={busy||!connected}>Discover tools</button>
                </form>
                <form className="stack" onSubmit={(e)=>{e.preventDefault();void action(async()=>{
                  const parsed=JSON.parse(mcpArguments) as Record<string,unknown>;
                  if(!parsed||Array.isArray(parsed)||typeof parsed!=="object") throw Error("Arguments must be a JSON object");
                  await api(token,"mcp/requests",{server_id:mcpServerId,tool:mcpTool,arguments:parsed});
                  setMcpRequests(await api<McpRequest[]>(token,"mcp/requests"));
                });}}>
                  <label>Connected server<select value={mcpServerId} onChange={(e)=>{setMcpServerId(e.target.value);setMcpTool("");}}><option value="">Choose a server</option>{mcpServers.map((s)=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
                  <label>Tool<select value={mcpTool} onChange={(e)=>setMcpTool(e.target.value)}><option value="">Choose a tool</option>{mcpServers.find((s)=>s.id===mcpServerId)?.tools.map((t)=><option key={t.name} value={t.name}>{t.name}</option>)}</select></label>
                  <label>Arguments (JSON)<textarea value={mcpArguments} onChange={(e)=>setMcpArguments(e.target.value)}/></label>
                  <button disabled={busy||!mcpTool}>Request tool approval</button>
                </form>
                {mcpRequests.map((r)=><div className="panel" key={r.id}><strong>{r.server} · {r.tool}</strong><pre>{JSON.stringify(r.arguments,null,2)}</pre><button onClick={()=>void action(async()=>{await api(token,"mcp/requests/"+r.id+"/approve",{});setMcpRequests(await api<McpRequest[]>(token,"mcp/requests"));})}>Approve once</button><button onClick={()=>void action(async()=>{await api(token,"mcp/requests/"+r.id+"/reject",{});setMcpRequests(await api<McpRequest[]>(token,"mcp/requests"));})}>Reject</button></div>)}
              </section>
              <section className="panel">
                <h2>Connect a model provider</h2>
                <p className="muted">Choose a local or hosted API. Keys are kept in this running gateway session.</p>
                <form className="stack" onSubmit={(e) => {e.preventDefault();void action(async () => {
                  const result=await api<{models:string[]}>(token,"providers/connect",{provider:providerId,endpoint:providerEndpoint||undefined,api_key:providerKey});
                  setProviderModels(result.models);setProviderModel(result.models[0]||"");setProviderKey("");
                  setProviders(await api<Provider[]>(token,"providers"));
                });}}>
                  <label>Provider<select value={providerId} onChange={(e)=>{setProviderId(e.target.value);setProviderEndpoint("");setProviderModels([]);}}>
                    {providers.map((p)=><option key={p.id} value={p.id}>{p.name}{p.connected?" · connected":""}</option>)}
                  </select></label>
                  <label>API endpoint<input value={providerEndpoint} onChange={(e)=>setProviderEndpoint(e.target.value)} placeholder={providers.find((p)=>p.id===providerId)?.default_endpoint||"http://127.0.0.1:PORT/v1"}/></label>
                  <label>API key, if required<input type="password" autoComplete="off" value={providerKey} onChange={(e)=>setProviderKey(e.target.value)}/></label>
                  <button className="primary" disabled={busy||!connected}>Test and connect</button>
                  {providerModels.length>0&&<p>Available models: {providerModels.slice(0,12).join(", ")}</p>}
                </form>
                {providerModels.length>0&&<form className="stack" onSubmit={(e)=>{e.preventDefault();void action(async()=>{
                  const result=await api<{text:string}>(token,"providers/"+providerId+"/chat",{model:providerModel,prompt:providerPrompt});
                  setProviderReply(result.text);
                });}}>
                  <label>Model<select value={providerModel} onChange={(e)=>setProviderModel(e.target.value)}>{providerModels.map((name)=><option key={name} value={name}>{name}</option>)}</select></label>
                  <label>Ask this model<textarea value={providerPrompt} onChange={(e)=>setProviderPrompt(e.target.value)} required maxLength={8000}/></label>
                  <button disabled={busy||!providerPrompt.trim()}>Send to provider</button>
                  {providerReply&&<pre>{providerReply}</pre>}
                </form>}
              </section>
              <div className="cards">
                {runtimes.map((r) => (
                  <section className="panel" key={r.id}>
                    <Plug className="accent" />
                    <h2>{r.name}</h2>
                    <span
                      className={
                        "badge " + (r.available ? "completed" : "failed")
                      }
                    >
                      {r.available
                        ? "Installed · execution requires approval"
                        : "Unavailable"}
                    </span>
                    <p>{r.permissions}</p>
                    <small>
                      {r.roots.join(", ") || "No approved workspace"}
                    </small>
                  </section>
                ))}
                <section className="panel">
                  <Smartphone className="accent" />
                  <h2>Android / HTTPS</h2>
                  <span className="badge completed">Android verified</span>
                  <p>
                    Use private Tailscale Serve. Keep the laptop online and
                    connect your Android phone to the same private network.
                  </p>
                </section>
              </div>
              <section className="panel">
                <h2>Request a runtime session</h2>
                <p className="muted">
                  Review and approve the exact request in Security before it
                  runs.
                </p>
                <form
                  className="stack"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action(async () => {
                      await api(token, "sessions", {
                        runtime: runtimeId,
                        root: runtimeRoot,
                        prompt: runtimePrompt,
                      });
                      setRuntimePrompt("");
                      setPage("Security");
                    });
                  }}
                >
                  <label>
                    Runtime
                    <select
                      value={runtimeId}
                      onChange={(e) => setRuntimeId(e.target.value)}
                    >
                      {runtimes.map((r) => (
                        <option key={r.id} value={r.id} disabled={!r.available}>
                          {r.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Approved workspace
                    <select
                      value={runtimeRoot}
                      onChange={(e) => setRuntimeRoot(e.target.value)}
                    >
                      <option value="">Choose a workspace</option>
                      {runtimes
                        .find((r) => r.id === runtimeId)
                        ?.roots.map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                    </select>
                  </label>
                  <label>
                    Goal
                    <textarea
                      value={runtimePrompt}
                      onChange={(e) => setRuntimePrompt(e.target.value)}
                      maxLength={8000}
                      required
                    />
                  </label>
                  <button
                    className="primary"
                    disabled={
                      busy ||
                      !connected ||
                      !runtimeRoot ||
                      !runtimePrompt.trim()
                    }
                  >
                    Create approval request
                  </button>
                </form>
              </section>
              <section className="panel">
                <h2>Runtime sessions</h2>
                {sessions.map((s) => (
                  <div className="session" key={s.id}>
                    <span className="badge">{s.status}</span>
                    <strong>{s.prompt}</strong>
                    <small>{s.root}</small>
                    {s.result && <pre>{s.result}</pre>}
                    {s.error && <p className="error">{s.error}</p>}
                    {["running", "queued"].includes(s.status) && (
                      <button
                        onClick={() =>
                          void action(() =>
                            api(token, "sessions/" + s.id + "/cancel", {}),
                          )
                        }
                      >
                        Cancel session
                      </button>
                    )}
                  </div>
                ))}
              </section>
            </>
          )}
          {page === "Automation" && (
            <>
              <section className="panel">
                <h2>Request an approved action</h2>
                <p className="muted">Each exact action expires after five minutes and can be approved only once.</p>
                <form className="stack" onSubmit={(e)=>{e.preventDefault();void action(async()=>{
                  const parsed=JSON.parse(automationArguments) as Record<string,unknown>;
                  if(!parsed||Array.isArray(parsed)||typeof parsed!=="object") throw Error("Arguments must be a JSON object");
                  await api(token,"automation/requests",{category:automationCategory,action:automationAction,arguments:parsed});
                  setAutomationArguments("{}");setPage("Security");
                });}}>
                  <label>Category<select value={automationCategory} onChange={(e)=>{const category=e.target.value as "windows"|"browser";setAutomationCategory(category);setAutomationAction(category==="windows"?"list_processes":"browser_create");}}><option value="windows">Windows</option><option value="browser">Browser</option></select></label>
                  <label>Action<select value={automationAction} onChange={(e)=>setAutomationAction(e.target.value)}>
                    {(automationCategory==="windows"?["list_files","file_metadata","read_text","list_processes","start_process","stop_process"]:["browser_create","browser_close","browser_navigate","browser_snapshot","browser_click","browser_fill","browser_screenshot"]).map((name)=><option key={name}>{name}</option>)}
                  </select></label>
                  <label>Exact arguments (JSON)<textarea aria-label="Exact automation arguments" value={automationArguments} onChange={(e)=>setAutomationArguments(e.target.value)} required/></label>
                  <button className="primary" disabled={busy||!automationHealth?.available}>Create approval request</button>
                </form>
              </section>
              <section className="panel"><h2>Automation tasks</h2>{automationRequests.length?automationRequests.map((r)=><article className="session" key={r.id}><span className={"badge "+r.status}>{r.status}</span><strong>{r.category} · {r.action}</strong><pre>{JSON.stringify(r.arguments,null,2)}</pre>{r.result!==null&&r.result!==undefined&&<pre>{JSON.stringify(r.result,null,2)}</pre>}{r.error&&<p className="error">{r.error}</p>}{["awaiting_approval","approved"].includes(r.status)&&<button onClick={()=>void action(()=>api(token,"automation/requests/"+r.id+"/cancel",{}))}>Cancel</button>}</article>):<div className="empty">No automation requests yet.</div>}</section>
            </>
          )}
          {page === "Security" && (
            <>
              <div className="cards">
                <section className="panel">
                  <Shield className="accent" />
                  <h2>Access boundary</h2>
                  <p>
                    Token authentication on every privileged API. Localhost by
                    default. No arbitrary shell endpoint.
                  </p>
                  <span className="badge">
                    {summary?.token_configured
                      ? "Token configured"
                      : "Connect to verify"}
                  </span>
                </section>
                <section className="panel">
                  <Lock className="accent" />
                  <h2>Runtime permissions</h2>
                  <p>
                    Allowlisted source-file reads only. No shell or write tools.
                    Each session requires approval. File contents and runtime
                    outputs are untrusted text.
                  </p>
                </section>
              </div>
              <section className="panel">
                <h2>Automation approvals</h2>
                {automationPending.length?automationPending.map((r)=><article className="session" key={r.id}><span className="eyebrow">{r.category} · {r.risk.toUpperCase()} RISK</span><h3>{r.action}</h3><pre>{JSON.stringify(r.arguments,null,2)}</pre><small>Expires {new Date(r.expires*1000).toLocaleString()} · digest {r.digest.slice(0,12)}…</small><div className="tools"><button className="primary" disabled={busy} onClick={()=>{const approval=window.prompt("Re-enter the Jarvis admin token to approve this exact digest: "+r.digest);if(approval)void action(()=>approveAutomation(token,r.id,r.digest,approval));}}>Approve once</button><button disabled={busy} onClick={()=>void action(()=>api(token,"automation/requests/"+r.id+"/reject",{}))}>Reject</button></div></article>):<div className="empty">No automation decisions waiting.</div>}
              </section>
              <section className="panel">
                <h2>Awaiting your approval</h2>
                {pending.length ? (
                  pending.map((s) => (
                    <article className="session" key={s.id}>
                      <span className="eyebrow">
                        {s.runtime} · READ-ONLY SESSION
                      </span>
                      <h3>{s.prompt}</h3>
                      <code>{s.root}</code>
                      <p>
                        The runtime can read this workspace. Review the prompt
                        before authorizing. The local Ollama model receives the
                        prompt and approved source-file contents.
                      </p>
                      <div className="tools">
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() =>
                            void action(() =>
                              api(token, "sessions/" + s.id + "/approve", {}),
                            )
                          }
                        >
                          Approve session
                        </button>
                        <button
                          disabled={busy}
                          onClick={() =>
                            void action(() =>
                              api(token, "sessions/" + s.id + "/reject", {}),
                            )
                          }
                        >
                          Reject
                        </button>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="empty">
                    <Shield />
                    <h3>No decisions waiting</h3>
                    <p>
                      New runtime requests will appear here before execution.
                    </p>
                  </div>
                )}
              </section>
            </>
          )}
          {page === "Settings" && (
            <section className="panel settings">
              <h2>Your workspace</h2>
              <label>
                Refresh interval
                <select
                  value={refresh}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    setRefresh(n);
                    localStorage.setItem("jarvis-refresh", String(n));
                  }}
                >
                  <option value={5}>5 seconds</option>
                  <option value={10}>10 seconds</option>
                  <option value={30}>30 seconds</option>
                </select>
              </label>
              <label>
                High contrast
                <input
                  type="checkbox"
                  checked={contrast}
                  onChange={(e) => setContrast(e.target.checked)}
                />
              </label>
              <div className="setting-row">
                <span>
                  Guided tour
                  <small>A focused walkthrough of your workspace</small>
                </span>
                <button onClick={() => setTour(0)}>
                  <Play size={14} /> Replay tour
                </button>
              </div>
              <div className="setting-row">
                <span>Persona concurrency</span>
                <strong>{summary?.concurrency ?? "—"}</strong>
              </div>
              <div className="setting-row">
                <span>Inference timeout</span>
                <strong>{summary?.timeout_seconds ?? "—"} seconds</strong>
              </div>
              <div className="setting-row">
                <span>Audit retention</span>
                <strong>{summary?.audit_retention ?? "—"} events</strong>
              </div>
              <p className="muted">
                Execution limits are server-controlled. Reduced motion follows
                your Windows accessibility preference.
              </p>
            </section>
          )}
          <footer>
            <span>LOCAL INTELLIGENCE. HUMAN CONTROL.</span>
            <span>Actual status · No simulated metrics</span>
          </footer>
        </main>
      </div>
      {compose && (
        <Modal title="Give your agent a task" onClose={() => setCompose(false)}>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              void action(async () => {
                await api(token, "jobs", { agent, prompt });
                setCompose(false);
                setPage("Tasks");
              });
            }}
          >
            <label>
              Persona
              <select
                id="agent"
                value={agent}
                onChange={(e) => setAgent(e.target.value)}
              >
                {Object.entries(names).map(([id, n]) => (
                  <option key={id} value={id}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label>
              What would you like done?
              <textarea
                id="prompt"
                autoFocus
                value={prompt}
                maxLength={8000}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe your goal and the result you need…"
                required
              />
            </label>
            <small>
              Text inference only · No tools · {prompt.length}/8000 characters
            </small>
            <button className="primary" disabled={busy || !prompt.trim()}>
              Queue task <ArrowUpRight size={16} />
            </button>
          </form>
        </Modal>
      )}
      {selected && (
        <Modal
          title="Task details"
          className="drawer"
          onClose={() => setSelected(null)}
        >
          {(() => {
            const j = jobs.find((x) => x.id === selected.id) || selected;
            return (
              <>
                <span className={"badge " + j.status}>{j.status}</span>
                <h3>{j.prompt}</h3>
                <dl>
                  <dt>Persona</dt>
                  <dd>{names[j.agent]}</dd>
                  <dt>Created</dt>
                  <dd>{date(j.created)}</dd>
                  <dt>Started</dt>
                  <dd>{date(j.started)}</dd>
                  <dt>Finished</dt>
                  <dd>{date(j.finished)}</dd>
                  <dt>Request stream closed</dt>
                  <dd>{date(j.stream_closed)}</dd>
                </dl>
                <h3>Output</h3>
                <pre>
                  {j.result ||
                    j.error ||
                    (j.status === "cancelled"
                      ? "Task cancelled. Model unload was not requested."
                      : "No output saved yet.")}
                </pre>
                <div className="tools">
                  {["queued", "running"].includes(j.status) && (
                    <button
                      className="danger"
                      disabled={busy}
                      onClick={() =>
                        void action(() =>
                          api(token, "jobs/" + j.id + "/cancel", {}),
                        )
                      }
                    >
                      Cancel task
                    </button>
                  )}
                  {["completed", "failed", "cancelled"].includes(j.status) && (
                    <button
                      onClick={() => {
                        setSelected(null);
                        newTask(j.agent, j.prompt);
                      }}
                    >
                      Retry as new task
                    </button>
                  )}
                </div>
              </>
            );
          })()}
        </Modal>
      )}
      {confirm && (
        <Modal title="Stop gateway tasks?" onClose={() => setConfirm(false)}>
          <p>
            This requests cancellation of queued and running persona tasks and runtime sessions.
            Windows stays running and models remain loaded. Pending approvals do not execute.
          </p>
          <div className="tools">
            <button onClick={() => setConfirm(false)}>Keep working</button>
            <button
              className="danger"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await api(token, "stop", {});
                  setConfirm(false);
                })
              }
            >
              Stop tasks
            </button>
          </div>
        </Modal>
      )}
      {help && (
        <Modal
          title="Your Jarvis guide"
          className="drawer"
          onClose={() => setHelp(false)}
        >
          <div className="guide-intro">
            <div className="avatar">
              <HelpCircle />
            </div>
            <h3>A little clarity, whenever you need it.</h3>
            <p>Instant guidance below works without an AI model.</p>
          </div>
          <input
            aria-label="Search help"
            placeholder="What do you need help with?"
            value={helpQuery}
            onChange={(e) => setHelpQuery(e.target.value)}
          />
          {helpTopics
            .filter((t) =>
              t.join(" ").toLowerCase().includes(helpQuery.toLowerCase()),
            )
            .map(([q, a]) => (
              <details key={q}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          <div className="tools">
            <button
              onClick={() => {
                setHelp(false);
                setTour(Number(localStorage.getItem("jarvis-tour-step") || 0));
              }}
            >
              Resume tour
            </button>
            <button
              onClick={() => {
                setHelp(false);
                setTour(0);
              }}
            >
              Replay tour
            </button>
          </div>
          <section className="help-ai">
            <h3>Need a more specific explanation?</h3>
            <p>
              Ask Rosie through the normal task queue. AI replies may be
              mistaken and cannot change your settings.
            </p>
            <button
              disabled={!connected}
              onClick={() => {
                setHelp(false);
                newTask(
                  "rosie",
                  "Help me understand this Jarvis workflow: " + helpQuery,
                );
              }}
            >
              Ask Rosie · AI help <ArrowUpRight size={15} />
            </button>
          </section>
        </Modal>
      )}
      {tour !== null && (
        <Modal
          title="Welcome to Jarvis"
          className="tour"
          onClose={() => setTour(null)}
        >
          <span className="eyebrow">
            GUIDED TOUR · {tour + 1} OF {steps.length}
          </span>
          <h3 ref={tourHeading} tabIndex={-1}>
            {steps[tour].title}
          </h3>
          <p>{steps[tour].text}</p>
          <div className="tour-progress">
            {steps.map((_, i) => (
              <span key={i} className={i === tour ? "current" : ""} />
            ))}
          </div>
          <div className="tools">
            <button onClick={() => setTour(null)}>Skip for now</button>
            {tour > 0 && (
              <button onClick={() => setTour(tour - 1)}>Back</button>
            )}
            <button
              className="primary"
              onClick={() => {
                if (tour === steps.length - 1) {
                  localStorage.setItem("jarvis-tour-done", "true");
                  setTour(null);
                } else setTour(tour + 1);
              }}
            >
              {tour === steps.length - 1 ? "Let’s begin" : "Next"}
              <ChevronRight size={15} />
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
