"""Authenticated approval and execution API for automation requests."""
import json
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from mcp import Client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from automation_models import AutomationRequest
from automation_store import (
    approve as approve_request,
    cancel as cancel_request,
    complete as complete_request,
    events,
    fail as fail_request,
    expire,
    get,
    list_requests,
    reject as reject_request,
    create,
)
from control import auth

router = APIRouter(
    prefix="/control/automation",
    dependencies=[Depends(auth)],
    tags=["Automation"],
)


def _not_found(operation):
    try:
        return operation()
    except KeyError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/requests")
def request_automation(request: AutomationRequest):
    expire()
    return create(request)


@router.get("/requests")
def automation_requests(status: str | None = Query(default=None, max_length=40)):
    expire()
    try:
        return list_requests(status)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.get("/requests/{request_id}")
def automation_request(request_id: str):
    expire()
    return _not_found(lambda: get(request_id))


@router.get("/requests/{request_id}/events")
def automation_request_events(request_id: str):
    _not_found(lambda: get(request_id))
    return events(request_id)


async def _call_adapter(row):
    url = os.environ.get("JARVIS_AUTOMATION_URL", "")
    secret = os.environ.get("JARVIS_AUTOMATION_SECRET", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or not parsed.port or parsed.username or parsed.password or len(secret) < 32):
        raise HTTPException(503, "Automation adapter is not securely configured")
    tool_name = ("windows_" + row["action"]
                 if row["category"] == "windows" else row["action"])
    http_client = create_mcp_http_client(
        headers={"Authorization": "Bearer " + secret}
    )
    async with http_client:
        transport = streamable_http_client(url, http_client=http_client)
        async with Client(transport, read_timeout_seconds=30) as client:
            result = await client.call_tool(tool_name, row["arguments"])
            data = result.model_dump(mode="json")
    texts = [item.get("text", "") for item in data.get("content", [])
             if item.get("type") == "text"]
    output = data.get("structured_content")
    if output is None:
        output = texts[0] if len(texts) == 1 else texts
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                pass
    normalized = {"output": output, "is_error": bool(data.get("is_error"))}
    if len(json.dumps(normalized).encode("utf-8")) > 65536:
        raise ValueError("Automation result too large")
    return normalized


@router.post("/requests/{request_id}/approve")
async def approve(request_id: str):
    expire()
    row = _not_found(lambda: get(request_id))
    _not_found(lambda: approve_request(request_id, row["digest"]))
    try:
        result = await _call_adapter(row)
        return complete_request(request_id, result)
    except HTTPException as exc:
        fail_request(request_id, exc.detail)
        raise
    except Exception:
        fail_request(request_id, "Automation adapter call failed")
        raise HTTPException(502, "Automation adapter call failed") from None


@router.post("/requests/{request_id}/reject")
def reject(request_id: str):
    expire()
    return _not_found(lambda: reject_request(request_id))


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: str):
    expire()
    return _not_found(lambda: cancel_request(request_id))


@router.get("/health")
async def automation_health():
    url = os.environ.get("JARVIS_AUTOMATION_URL", "")
    secret = os.environ.get("JARVIS_AUTOMATION_SECRET", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or not parsed.port or len(secret) < 32):
        return {"available": False, "actions": [], "reason": "Adapter is not configured"}
    try:
        http_client = create_mcp_http_client(
            headers={"Authorization": "Bearer " + secret}
        )
        async with http_client:
            transport = streamable_http_client(url, http_client=http_client)
            async with Client(transport, read_timeout_seconds=5) as client:
                result = await client.list_tools()
                actions = [tool.name for tool in result.tools]
        return {"available": True, "actions": actions}
    except Exception:
        return {"available": False, "actions": [], "reason": "Adapter is unavailable"}
