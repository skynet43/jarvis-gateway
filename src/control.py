"""Authenticated local control plane. Personas have no tools."""
import hmac
import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

LOCK = threading.RLock()
DB = Path(os.environ.get("JARVIS_DB", str(Path(__file__).resolve().parent.parent / "data" / "jarvis.db")))
TEMPLATES = {"rosie": "Assistant", "benson": "Coordinator", "mr-belvedere": "Maintenance"}
MODEL = "tool-star-qwen:3b"
ACTIVE = ("queued", "running", "cancelling")
def now():
    return datetime.now(timezone.utc).isoformat()
@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=10)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at TEXT, action TEXT, details TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, agent TEXT, prompt TEXT, status TEXT, created TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS job_results (id TEXT PRIMARY KEY, result TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS configured_agents (id TEXT PRIMARY KEY,role TEXT NOT NULL,model TEXT NOT NULL)")
        if not db.execute("SELECT 1 FROM configured_agents LIMIT 1").fetchone() and (db.execute("SELECT 1 FROM jobs LIMIT 1").fetchone() or os.environ.get("JARVIS_TEST_TEMPLATES")=="1"):
            db.executemany("INSERT OR IGNORE INTO configured_agents VALUES(?,?,?)",[(key,role,MODEL) for key,role in TEMPLATES.items()])
        columns = {r[1] for r in db.execute("PRAGMA table_info(jobs)")}
        for col in ("started", "updated", "finished", "error", "stream_closed"):
            if col not in columns:
                db.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
        db.execute("CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status,created)")
        db.execute("PRAGMA user_version=1")
        db.commit()
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
def record(db, action, details):
    db.execute("INSERT INTO audit(at,action,details) VALUES(?,?,?)", (now(), action, json.dumps(details)))
    db.execute("DELETE FROM audit WHERE id <= (SELECT COALESCE(MAX(id),0)-10000 FROM audit)")
def audit(action, details):
    with LOCK, connect() as db:
        record(db, action, details)
def auth(request: Request, x_jarvis_token: str | None = Header(default=None)):
    from browser_session import valid
    if valid(request):
        return
    token = os.environ.get("JARVIS_ADMIN_TOKEN", "")
    if not token:
        raise HTTPException(503, "Admin token is not configured")
    if not x_jarvis_token or not hmac.compare_digest(token.encode(), x_jarvis_token.encode()):
        raise HTTPException(401, "Invalid control token")
router = APIRouter(prefix="/control", tags=["Control Plane"], dependencies=[Depends(auth)])
class JobRequest(BaseModel):
    agent: str = Field(max_length=40)
    prompt: str = Field(min_length=1, max_length=8000)
class Job(BaseModel):
    id: str
    agent: str
    prompt: str
    status: Literal["queued", "running", "cancelling", "cancelled", "completed", "failed"]
    created: str
    started: str | None = None
    updated: str | None = None
    finished: str | None = None
    error: str | None = None
    stream_closed: str | None = None
    result: str | None = None
@router.get("/agents")
def agents():
    with LOCK, connect() as db:
        rows=db.execute("SELECT id,role,model FROM configured_agents ORDER BY id").fetchall()
    return [{"id": key,"role":role,"capabilities":["Text inference"],"tool_access":False,"model":model} for key,role,model in rows]
class AgentSetup(BaseModel):
    templates:list[Literal["rosie","benson","mr-belvedere"]]=Field(default_factory=list,max_length=3)
@router.post("/agents/setup")
def setup_agents(req:AgentSetup):
    with LOCK,connect() as db:
        for key in dict.fromkeys(req.templates):
            db.execute("INSERT OR IGNORE INTO configured_agents VALUES(?,?,?)",(key,TEMPLATES[key],MODEL))
        record(db,"agents.configured",{"templates":list(dict.fromkeys(req.templates))})
    return agents()
@router.post("/jobs", response_model=Job)
def submit(req: JobRequest):
    if req.agent not in {item["id"] for item in agents()}:
        raise HTTPException(404, "Unknown agent")
    if not req.prompt.strip():
        raise HTTPException(422, "Prompt cannot be blank")
    stamp = now()
    job = dict(id=str(uuid.uuid4()), agent=req.agent, prompt=req.prompt, status="queued", created=stamp, updated=stamp)
    with LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','cancelling')").fetchone()[0] >= 50:
            raise HTTPException(429, "Queue is full (50 active tasks)")
        db.execute("INSERT INTO jobs(id,agent,prompt,status,created,updated) VALUES(:id,:agent,:prompt,:status,:created,:updated)", job)
        record(db, "job.created", {"id":job["id"], "agent":req.agent})
    return job
@router.get("/jobs", response_model=list[Job])
def jobs(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), status: str | None = None, q: str = Query("", max_length=200)):
    with LOCK, connect() as db:
        db.row_factory = sqlite3.Row
        return [dict(x) for x in db.execute(
            "SELECT jobs.*,job_results.result FROM jobs LEFT JOIN job_results ON jobs.id=job_results.id WHERE (? IS NULL OR status=?) AND prompt LIKE ? ORDER BY created DESC,id DESC LIMIT ? OFFSET ?",
            (status or None,status or None,"%"+q+"%",limit,offset))]
@router.get("/jobs/{job_id}", response_model=Job)
def detail(job_id: str):
    with LOCK, connect() as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT jobs.*,job_results.result FROM jobs LEFT JOIN job_results ON jobs.id=job_results.id WHERE jobs.id=?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Task not found")
        return dict(row)
def request_cancel(db, job_id):
    stamp=now()
    result=db.execute("UPDATE jobs SET status=CASE WHEN status='queued' THEN 'cancelled' ELSE 'cancelling' END, updated=?, finished=CASE WHEN status='queued' THEN ? ELSE NULL END WHERE id=? AND status IN ('queued','running')", (stamp,stamp,job_id))
    if not result.rowcount:
        raise HTTPException(409, "Task missing or no longer cancellable")
    status=db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
    record(db, "job.cancelled" if status=="cancelled" else "job.cancel_requested", {"id":job_id})
    return {"id":job_id,"status":status}
@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str):
    with LOCK, connect() as db:
        return request_cancel(db,job_id)
@router.post("/stop")
def stop_all():
    with LOCK, connect() as db:
        ids=[r[0] for r in db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')")]
        for job_id in ids:
            request_cancel(db,job_id)
        from harness import init, event
        init(db)
        runtime_ids=[r[0] for r in db.execute("SELECT id FROM sessions WHERE status IN ('queued','running')")]
        for sid in runtime_ids:
            db.execute("UPDATE sessions SET status=CASE WHEN status='running' THEN 'cancelling' ELSE 'cancelled' END,updated=? WHERE id=?",(now(),sid))
            event(db,sid,"cancel_requested",{})
        return {"requested":len(ids)+len(runtime_ids),"persona_tasks":len(ids),"runtime_sessions":len(runtime_ids),"scope":"All gateway tasks and runtime sessions; no model unload or system shutdown"}
@router.get("/audit")
def audit_events(after: int = Query(0,ge=0), limit: int = Query(100,ge=1,le=500)):
    with LOCK, connect() as db:
        db.row_factory=sqlite3.Row
        return [dict(x) for x in db.execute("SELECT * FROM audit WHERE id>? ORDER BY id DESC LIMIT ?",(after,limit))]
@router.get("/summary")
def summary():
    with LOCK, connect() as db:
        counts=dict(db.execute("SELECT status,COUNT(*) FROM jobs GROUP BY status"))
        last=db.execute("SELECT COALESCE(MAX(id),0) FROM audit").fetchone()[0]
    return {"counts":counts, "event_id":last,"model":MODEL,"concurrency":1,"timeout_seconds":120,"audit_retention":10000,"queue_limit":50,"token_configured":bool(os.environ.get("JARVIS_ADMIN_TOKEN")),"tool_access":False,"approved_roots":[],"mcp":"Not configured","unload_supported":False}
