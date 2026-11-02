"""Local-only control-plane: auth, SQLite audit, agents and safe task queue."""
import hmac
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/control", tags=["Control Plane"])
DB = Path(__file__).resolve().parent.parent / "data" / "jarvis.db"
LOCK = threading.RLock()
AGENTS = {"rosie": "Assistant", "benson": "Coordinator", "mr-belvedere": "Maintenance"}
def now():
    return datetime.now(timezone.utc).isoformat()
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at TEXT, action TEXT, details TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, agent TEXT, prompt TEXT, status TEXT, created TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS job_results (id TEXT PRIMARY KEY, result TEXT)")
    db.commit()
    return db
def audit(action, details):
    with LOCK, connect() as db:
        db.execute("INSERT INTO audit(at,action,details) VALUES(?,?,?)", (now(), action, json.dumps(details)))
def auth(x_jarvis_token: str | None = Header(default=None)):
    token = os.environ.get("JARVIS_ADMIN_TOKEN", "")
    if not token:
        raise HTTPException(503, "Set JARVIS_ADMIN_TOKEN before using control operations")
    if not x_jarvis_token or not hmac.compare_digest(token, x_jarvis_token):
        raise HTTPException(401, "Invalid control token")
class JobRequest(BaseModel):
    agent: str
    prompt: str = Field(min_length=1, max_length=8000)
@router.get("/agents", dependencies=[Depends(auth)])
def agents():
    return [{"id": k, "role": v} for k,v in AGENTS.items()]
@router.post("/jobs", dependencies=[Depends(auth)])
def submit(req: JobRequest):
    if req.agent not in AGENTS:
        raise HTTPException(404, "Unknown agent")
    job = {"id": str(uuid.uuid4()), "agent": req.agent, "prompt": req.prompt, "status": "queued", "created": now()}
    with LOCK, connect() as db:
        db.execute("INSERT INTO jobs VALUES(:id,:agent,:prompt,:status,:created)", job)
    audit("job.created", {"id": job["id"], "agent": req.agent})
    return job
@router.get("/jobs", dependencies=[Depends(auth)])
def jobs():
    with LOCK, connect() as db:
        db.row_factory = sqlite3.Row
        return [dict(x) for x in db.execute("SELECT jobs.*,job_results.result FROM jobs LEFT JOIN job_results ON jobs.id=job_results.id ORDER BY jobs.created DESC LIMIT 100")]
@router.post("/jobs/{job_id}/cancel", dependencies=[Depends(auth)])
def cancel(job_id: str):
    with LOCK, connect() as db:
        result = db.execute("UPDATE jobs SET status='cancelled' WHERE id=? AND status IN ('queued','running')", (job_id,))
        if not result.rowcount:
            raise HTTPException(409, "Job missing or no longer cancellable")
    audit("job.cancelled", {"id": job_id})
    return {"id": job_id, "status": "cancelled"}
@router.get("/audit", dependencies=[Depends(auth)])
def audit_events():
    with LOCK, connect() as db:
        db.row_factory = sqlite3.Row
        return [dict(x) for x in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")]
