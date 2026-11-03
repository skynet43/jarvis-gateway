"""Authenticated approval-state API for automation requests."""
from fastapi import APIRouter, Depends, HTTPException, Query

from automation_models import AutomationRequest
from automation_store import (
    approve as approve_request,
    cancel as cancel_request,
    events,
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


@router.post("/requests/{request_id}/approve")
def approve(request_id: str):
    expire()
    row = _not_found(lambda: get(request_id))
    return _not_found(lambda: approve_request(request_id, row["digest"]))


@router.post("/requests/{request_id}/reject")
def reject(request_id: str):
    expire()
    return _not_found(lambda: reject_request(request_id))


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: str):
    expire()
    return _not_found(lambda: cancel_request(request_id))
