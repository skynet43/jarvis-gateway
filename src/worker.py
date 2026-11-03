"""Single FIFO worker; async cancellation closes the HTTP stream before acknowledgement."""
import asyncio
import json
import os
import threading
import httpx
from upstream import bounded_lines
from control import LOCK, MODEL, connect, now, record

def recover():
    with LOCK, connect() as db:
        rows=list(db.execute("SELECT id,status FROM jobs WHERE status IN ('running','cancelling')"))
        for job_id,status in rows:
            final="cancelled" if status=="cancelling" else "failed"
            db.execute("UPDATE jobs SET status=?,updated=?,finished=?,error=? WHERE id=?", (final,now(),now(),"Gateway restarted before completion; inference stop not verified",job_id))
            record(db,"job.recovered",{"id":job_id,"status":final})
def claim():
    with LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT id,agent,prompt FROM jobs WHERE status='queued' ORDER BY created,id LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE jobs SET status='running',started=?,updated=? WHERE id=? AND status='queued'",(now(),now(),row[0]))
            record(db,"job.started",{"id":row[0]})
        return row
async def infer(agent,prompt):
    answer=""
    async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=5),trust_env=False) as client:
        async with client.stream("POST",os.environ.get("JARVIS_OLLAMA_URL","http://127.0.0.1:11434").rstrip("/")+"/api/chat",json={
            "model":MODEL,"stream":True,"options":{"num_predict":4096},
            "messages":[{"role":"system","content":"You are "+agent+". Respond to the task. You have no tool access."},{"role":"user","content":prompt}]
        }) as response:
            response.raise_for_status()
            async for line in bounded_lines(response):
                if not line:
                    continue
                if len(line)>262144:
                    raise ValueError("Model packet exceeded limit")
                packet=json.loads(line)
                if packet.get("error"):
                    raise ValueError("Ollama returned an inference error")
                answer+=packet.get("message",{}).get("content","")
                if len(answer)>262144:
                    raise ValueError("Model output exceeded limit")
                if packet.get("done"):
                    return answer
    raise ValueError("Ollama stream ended before completion")
async def process_one(stop=None):
    row=claim()
    if not row:
        return False
    job_id,agent,prompt=row
    task=asyncio.create_task(asyncio.wait_for(infer(agent,prompt),timeout=120))
    answer=""
    status="completed"
    error=None
    try:
        while not task.done():
            with LOCK, connect() as db:
                current=db.execute("SELECT status FROM jobs WHERE id=?",(job_id,)).fetchone()
            if not current or current[0]=="cancelling" or (stop and stop.is_set()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                status="cancelled" if current and current[0]=="cancelling" else "failed"
                error=None if status=="cancelled" else "Gateway shut down during inference"
                break
            await asyncio.sleep(0.1)
        if status=="completed":
            answer=await task
    except (TimeoutError,httpx.TimeoutException):
        status,error="failed","Inference timed out"
    except Exception as exc:
        status,error="failed","Inference failed ("+type(exc).__name__+")"
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    with LOCK, connect() as db:
        stamp=now()
        updated=db.execute(
            "UPDATE jobs SET status=CASE WHEN status='cancelling' THEN 'cancelled' ELSE ? END,"
            "updated=?,finished=?,error=CASE WHEN status='cancelling' THEN NULL ELSE ? END,stream_closed=? "
            "WHERE id=? AND status IN ('running','cancelling')",
            (status,stamp,stamp,error,stamp,job_id))
        if updated.rowcount:
            status=db.execute("SELECT status FROM jobs WHERE id=?",(job_id,)).fetchone()[0]
            if status=="completed":
                db.execute("INSERT OR REPLACE INTO job_results VALUES (?,?)",(job_id,answer))
            record(db,"job."+status,{"id":job_id,"request_stream_closed":True,"inference_stopped":"unverified","model_unloaded":False})
    return True
def start():
    recover()
    stop=threading.Event()
    async def loop():
        while not stop.is_set():
            try:
                if not await process_one(stop):
                    await asyncio.sleep(.25)
            except Exception as exc:
                import logging
                logging.getLogger("jarvis.worker").error("worker_cycle_failed type=%s",type(exc).__name__)
                await asyncio.sleep(1)
    thread=threading.Thread(target=lambda:asyncio.run(loop()),daemon=True,name="jarvis-local-worker")
    thread.start()
    return stop,thread
