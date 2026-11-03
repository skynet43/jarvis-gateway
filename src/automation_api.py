"""Authenticated approval and execution API for automation requests."""
import hmac
import json
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
import httpx
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


def _adapter_emergency():
    url = os.environ.get("JARVIS_AUTOMATION_URL", "")
    secret = os.environ.get("JARVIS_AUTOMATION_SECRET", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or not parsed.port or len(secret) < 32):
        return None, None
    return parsed._replace(path="/emergency-stop", query="", fragment="").geturl(), secret


async def interrupt_active_adapter():
    url, secret = _adapter_emergency()
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.post(url, headers={"Authorization": "Bearer " + secret})
        return response.status_code == 200
    except Exception:
        return False


def interrupt_active_adapter_sync():
    url, secret = _adapter_emergency()
    if not url:
        return False
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.post(url, headers={"Authorization": "Bearer " + secret})
        return response.status_code == 200
    except Exception:
        return False


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


class ApprovalDecision(BaseModel):
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.post("/requests/{request_id}/approve")
async def approve(
    request_id: str,
    decision: ApprovalDecision,
    x_jarvis_approval: str | None = Header(default=None),
):
    configured = os.environ.get("JARVIS_ADMIN_TOKEN", "")
    if (not configured or not x_jarvis_approval
            or not hmac.compare_digest(configured.encode(), x_jarvis_approval.encode())):
        raise HTTPException(401, "Explicit approval authentication required")
    expire()
    row = _not_found(lambda: get(request_id))
    if not hmac.compare_digest(row["digest"], decision.digest):
        raise HTTPException(409, "Approval digest does not match the reviewed request")
    _not_found(lambda: approve_request(request_id, decision.digest))
    try:
        result = await _call_adapter(row)
        return complete_request(request_id, result)
    except HTTPException as exc:
        if get(request_id)["status"] == "cancelled":
            return get(request_id)
        fail_request(request_id, exc.detail)
        raise
    except Exception:
        if get(request_id)["status"] == "cancelled":
            return get(request_id)
        fail_request(request_id, "Automation adapter call failed")
        raise HTTPException(502, "Automation adapter call failed") from None


@router.post("/requests/{request_id}/reject")
def reject(request_id: str):
    expire()
    return _not_found(lambda: reject_request(request_id))


@router.post("/requests/{request_id}/cancel")
async def cancel(request_id: str):
    expire()
    row = _not_found(lambda: cancel_request(request_id))
    if row["status"] == "cancelled":
        await interrupt_active_adapter()
    return row


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
