"""Loopback-only Jarvis Gateway and Command Center."""
import asyncio
import json
import os
import subprocess
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
import httpx
from upstream import bounded_json, bounded_lines
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from control import auth, router as control_router, audit_events, LOCK, connect

HOST="127.0.0.1"
PORT=8765
OLLAMA_BASE_URL=os.environ.get("JARVIS_OLLAMA_URL","http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL="qwen2.5-coder:7b"
DIST=Path(__file__).resolve().parent.parent/"frontend"/"dist"
@asynccontextmanager
async def lifespan(app):
    from worker import start
    stop,thread=start()
    from harness import start as start_harness
    harness_stop,harness_thread=start_harness()
    try:
        yield
    finally:
        stop.set()
        harness_stop.set()
        await asyncio.to_thread(thread.join,10)
        await asyncio.to_thread(harness_thread.join,10)
app=FastAPI(lifespan=lifespan,title="Jarvis Gateway",version="0.2.0")
app.include_router(control_router)
from browser_session import router as browser_router
app.include_router(browser_router)
from harness import router as harness_router
app.include_router(harness_router)
from providers import router as providers_router
app.include_router(providers_router)
from mcp_bridge import router as mcp_router
app.include_router(mcp_router)
from automation_api import router as automation_router
app.include_router(automation_router)
buckets=defaultdict(deque)
@app.middleware("http")
async def guard(request: Request, call_next):
    host=request.url.hostname
    remote_origin=os.environ.get("JARVIS_HTTPS_ORIGIN","").rstrip("/")
    remote_host=urlsplit(remote_origin).hostname if remote_origin.startswith("https://") else None
    if host not in ("127.0.0.1","localhost","::1",remote_host):
        return JSONResponse({"detail":"Local host required"},400)
    origin=request.headers.get("origin")
    allowed_origins={str(request.base_url).rstrip("/")}
    if remote_origin and host==remote_host:
        allowed_origins.add(remote_origin)
    if origin and origin not in allowed_origins:
        return JSONResponse({"detail":"Cross-origin requests are forbidden"},403)
    if request.headers.get("sec-fetch-site")=="cross-site":
        return JSONResponse({"detail":"Cross-site requests are forbidden"},403)
    if request.method in ("POST","PUT","PATCH"):
        try:
            if int(request.headers.get("content-length","0"))>65536:
                return JSONResponse({"detail":"Request too large"},413)
        except ValueError:
            return JSONResponse({"detail":"Invalid content length"},400)
        size=0
        parts=[]
        async for chunk in request.stream():
            size+=len(chunk)
            if size>65536:
                return JSONResponse({"detail":"Request too large"},413)
            parts.append(chunk)
        request._body=b"".join(parts)
    if request.url.path.startswith(("/control","/ollama")):
        key="local"
        queue=buckets[key]
        stamp=time.monotonic()
        while queue and stamp-queue[0]>60:
            queue.popleft()
        if len(queue)>=600:
            return JSONResponse({"detail":"Request rate exceeded; retry shortly"},429,headers={"Retry-After":"60"})
        queue.append(stamp)
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Cache-Control"]="no-store"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response
@app.get("/")
def root():
    return {"service":"Jarvis Gateway","host":HOST,"port":PORT,"ollama":OLLAMA_BASE_URL,"default_model":DEFAULT_MODEL}
@app.get("/health")
def health():
    return {"status":"ok"}
@app.get("/dashboard",include_in_schema=False)
def dashboard():
    path=DIST/"index.html"
    return FileResponse(path if path.exists() else Path(__file__).with_name("dashboard.html"))
if (DIST/"assets").exists():
    app.mount("/assets",StaticFiles(directory=DIST/"assets"),name="assets")
class ChatMessage(BaseModel):
    role: str=Field(max_length=30)
    content: str=Field(max_length=8000)
class ChatRequest(BaseModel):
    message: str | None=Field(default=None,max_length=8000)
    messages: list[ChatMessage] | None=Field(default=None,max_length=64)
    model: str=Field(default=DEFAULT_MODEL,max_length=200)
    stream: bool=False
async def ollama_json(path, payload=None):
    try:
        async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
            async with client.stream("GET" if payload is None else "POST",OLLAMA_BASE_URL+path,json=payload) as response:
                return await bounded_json(response,2097152)
    except (httpx.HTTPError,ValueError):
        raise HTTPException(502,"Ollama is unavailable or returned invalid data")
@app.get("/ollama/models",dependencies=[Depends(auth)])
async def ollama_models():
    return await ollama_json("/api/tags")
@app.post("/ollama/chat",dependencies=[Depends(auth)])
async def ollama_chat(request: ChatRequest):
    messages=request.messages
    if messages is None:
        if not request.message:
            raise HTTPException(400,"Provide either message or messages")
        messages=[ChatMessage(role="user",content=request.message)]
    payload={"model":request.model,"messages":[m.model_dump() for m in messages],"stream":request.stream,"options":{"num_predict":4096}}
    if not request.stream:
        try:
            async with httpx.AsyncClient(timeout=120,trust_env=False) as client:
                async with client.stream("POST",OLLAMA_BASE_URL+"/api/chat",json=payload) as response:
                    response.raise_for_status()
                    data=bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data)>1048576:
                            raise HTTPException(502,"Upstream response exceeded limit")
                    return json.loads(data)
        except (httpx.HTTPError,ValueError):
            raise HTTPException(502,"Ollama inference failed")
    async def chunks():
        async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
            try:
                async with asyncio.timeout(120):
                    async with client.stream("POST",OLLAMA_BASE_URL+"/api/chat",json=payload) as response:
                        response.raise_for_status()
                        size=0
                        async for line in bounded_lines(response):
                            size+=len(line)
                            if size>1048576:
                                raise ValueError("Output limit")
                            yield line+"\n"
            except (httpx.HTTPError,ValueError,TimeoutError):
                yield json.dumps({"error":"Upstream stream failed"})+"\n"
    return StreamingResponse(chunks(),media_type="application/x-ndjson")
@app.get("/control/models",dependencies=[Depends(auth)])
async def models():
    try:
        installed,loaded=await asyncio.gather(ollama_json("/api/tags"),ollama_json("/api/ps"))
        return {"available":True,"installed":installed.get("models",[]),"loaded":loaded.get("models",[]),"unload_supported":False,"unload_reason":"Ollama does not establish exclusive session ownership; unload is disabled."}
    except HTTPException:
        return {"available":False,"installed":[],"loaded":[],"error":"Ollama is unavailable","unload_supported":False}
@app.get("/control/telemetry",dependencies=[Depends(auth)])
async def telemetry():
    def probe():
        try:
            result=subprocess.run(["nvidia-smi","--query-gpu=name,utilization.gpu,memory.used,memory.total","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=3,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if result.returncode:
                raise ValueError()
            values=result.stdout.strip().splitlines()[0].split(",")
            return {"available":True,"name":values[0].strip(),"utilization":float(values[1]),"memory_used_mib":float(values[2]),"memory_total_mib":float(values[3]),"scope":"Whole GPU, not exclusively Jarvis"}
        except (OSError,ValueError,IndexError,subprocess.TimeoutExpired):
            return {"available":False,"reason":"NVIDIA telemetry unavailable"}
    return await asyncio.to_thread(probe)
@app.get("/control/events",dependencies=[Depends(auth)])
async def events(request: Request, after: int=0):
    try:
        cursor=max(after,int(request.headers.get("last-event-id","0")))
    except ValueError:
        raise HTTPException(400,"Invalid event cursor")
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with LOCK, connect() as db:
                import sqlite3
                db.row_factory=sqlite3.Row
                rows=[dict(r) for r in db.execute("SELECT * FROM audit WHERE id>? ORDER BY id LIMIT 500",(cursor,))]
            if rows:
                for row in rows:
                    cursor=row["id"]
                    yield f"id: {cursor}\ndata: {json.dumps(row)}\n\n"
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"X-Accel-Buffering":"no"})
if __name__=="__main__":
    uvicorn.run("gateway:app",host=HOST,port=PORT,reload=False)
