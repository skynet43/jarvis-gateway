"""Loopback MCP discovery with one-use, explicit tool-call approvals."""
import json
import secrets
import time
from urllib.parse import urlsplit
from mcp import Client
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from control import LOCK, auth, connect, record

router=APIRouter(prefix="/control/mcp",dependencies=[Depends(auth)],tags=["MCP"])
SERVERS={}
PENDING={}

class ServerRequest(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    url:str=Field(max_length=512)

def safe_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1") or not parsed.port:
        raise HTTPException(400,"MCP server must use loopback HTTP")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(400,"MCP URL cannot contain credentials or query parameters")
    return url

@router.get("/servers")
def servers():
    return [{"id":id,"name":row["name"],"url":row["url"],"tools":row["tools"]} for id,row in SERVERS.items()]

@router.post("/servers")
async def add_server(req:ServerRequest):
    url=safe_url(req.url)
    try:
        async with Client(url,read_timeout_seconds=8) as client:
            result=await client.list_tools()
    except Exception:
        raise HTTPException(502,"MCP discovery failed") from None
    tools=[{"name":t.name,"description":(t.description or "")[:500],"input_schema":t.input_schema} for t in result.tools[:100]]
    id=secrets.token_urlsafe(12)
    SERVERS[id]={"name":req.name,"url":url,"tools":tools}
    with LOCK,connect() as db:record(db,"mcp.server_added",{"id":id,"name":req.name,"tools":len(tools)})
    return {"id":id,"name":req.name,"tools":tools}

class ToolRequest(BaseModel):
    server_id:str
    tool:str
    arguments:dict=Field(default_factory=dict)

@router.post("/requests")
def request_tool(req:ToolRequest):
    server=SERVERS.get(req.server_id)
    if not server or req.tool not in {t["name"] for t in server["tools"]}:
        raise HTTPException(404,"MCP tool is not connected")
    if len(json.dumps(req.arguments))>8192:
        raise HTTPException(413,"Tool arguments too large")
    id=secrets.token_urlsafe(18)
    PENDING[id]={"server_id":req.server_id,"tool":req.tool,"arguments":req.arguments,"expires":time.monotonic()+300}
    with LOCK,connect() as db:record(db,"mcp.approval_requested",{"id":id,"server_id":req.server_id,"tool":req.tool})
    return {"id":id,"status":"awaiting_approval","server":server["name"],"tool":req.tool,"arguments":req.arguments}

@router.get("/requests")
def pending_requests():
    return [{"id":id,"server":SERVERS[row["server_id"]]["name"],"tool":row["tool"],"arguments":row["arguments"]} for id,row in PENDING.items() if row["expires"]>time.monotonic() and row["server_id"] in SERVERS]

@router.post("/requests/{id}/reject")
def reject(id:str):
    if not PENDING.pop(id,None):raise HTTPException(404,"Request expired")
    with LOCK,connect() as db:record(db,"mcp.rejected",{"id":id})
    return {"id":id,"status":"rejected"}

@router.post("/requests/{id}/approve")
async def approve(id:str):
    row=PENDING.pop(id,None)
    if not row or row["expires"]<time.monotonic():raise HTTPException(404,"Request expired")
    server=SERVERS.get(row["server_id"])
    if not server:raise HTTPException(404,"Server disconnected")
    with LOCK,connect() as db:record(db,"mcp.approved",{"id":id,"tool":row["tool"]})
    try:
        async with Client(server["url"],read_timeout_seconds=30) as client:
            result=await client.call_tool(row["tool"],row["arguments"])
            data=result.model_dump(mode="json")
    except Exception:
        with LOCK,connect() as db:record(db,"mcp.failed",{"id":id})
        raise HTTPException(502,"MCP tool call failed") from None
    encoded=json.dumps(data)
    if len(encoded)>65536:raise HTTPException(502,"MCP result too large")
    with LOCK,connect() as db:record(db,"mcp.completed",{"id":id,"error":bool(data.get("isError"))})
    return {"id":id,"status":"completed","result":data}
