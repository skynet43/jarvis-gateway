"""Local Ollama streaming worker with cooperative cancellation."""
import json
import threading
import requests
from control import LOCK, audit, connect
MODEL = "tool-star-qwen:3b"

def is_cancelled(job_id):
    with LOCK, connect() as db:
        row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        return row is None or row[0] == "cancelled"

def process_one():
    with LOCK, connect() as db:
        row = db.execute("SELECT id,agent,prompt FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row:
            return False
        job_id, agent, prompt = row
        db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (job_id,))
    audit("job.started", {"id": job_id})
    answer = ""
    status = "completed"
    try:
        with requests.post("http://127.0.0.1:11434/api/chat", json={
            "model": MODEL, "stream": True,
            "messages": [{"role":"system","content":"You are "+agent+". Respond to the task. You have no tool access."},
                         {"role":"user","content":prompt}]}, stream=True, timeout=(5, 30)) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if is_cancelled(job_id):
                    status = "cancelled"
                    break
                if not line:
                    continue
                packet = json.loads(line)
                answer += packet.get("message",{}).get("content","")
                if packet.get("done"):
                    break
    except Exception as exc:
        status = "failed"
        answer = str(exc)[:1000]
    with LOCK, connect() as db:
        row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row and row[0] == "cancelled":
            status = "cancelled"
        else:
            db.execute("INSERT OR REPLACE INTO job_results VALUES (?,?)", (job_id, answer))
            db.execute("UPDATE jobs SET status=? WHERE id=? AND status='running'", (status,job_id))
    if status != "cancelled":
        audit("job."+status, {"id":job_id})
    return True

def loop(stop):
    while not stop.is_set():
        try:
            if not process_one():
                stop.wait(1)
        except Exception:
            stop.wait(2)

def start():
    stop = threading.Event()
    thread = threading.Thread(target=loop,args=(stop,),daemon=True,name="jarvis-local-worker")
    thread.start()
    return stop
