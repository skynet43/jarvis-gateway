"""Automatic same-origin desktop sessions. No admin secret enters the browser."""
import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from urllib.parse import urlsplit
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

router=APIRouter()
KEY=secrets.token_bytes(32)
COOKIE="jarvis_browser_session"
LOCAL_HOSTS={"127.0.0.1","localhost","::1"}
TAILNET_RANGES=(ipaddress.ip_network("100.64.0.0/10"),ipaddress.ip_network("fd7a:115c:a1e0::/48"))
def tailnet_address(value:str):
    try:return any(ipaddress.ip_address(value) in network for network in TAILNET_RANGES)
    except ValueError:return False
def valid(request: Request):
    value=request.cookies.get(COOKIE,"")
    try:
        expires,signature=value.split(".",1)
        message=(expires+"|"+str(request.url.hostname)).encode()
        return int(expires)>time.time() and hmac.compare_digest(signature,hmac.new(KEY,message,hashlib.sha256).hexdigest())
    except (ValueError,TypeError):
        return False
@router.post("/control/browser-session")
def open_session(
    request: Request,
    x_jarvis_token: str | None = Header(default=None),
):
    host=request.url.hostname
    remote_origin=os.environ.get("JARVIS_HTTPS_ORIGIN","").rstrip("/")
    remote_host=urlsplit(remote_origin).hostname if remote_origin.startswith("https://") else None
    owner=os.environ.get("JARVIS_TAILSCALE_LOGIN","")
    local=host in LOCAL_HOSTS and request.client and request.client.host in LOCAL_HOSTS
    configured=os.environ.get("JARVIS_ADMIN_TOKEN","")
    local_authenticated=(local and configured and x_jarvis_token
                         and hmac.compare_digest(configured.encode(),x_jarvis_token.encode()))
    private_remote=(remote_host and host==remote_host and request.client and tailnet_address(request.client.host)
                    and owner and hmac.compare_digest(request.headers.get("tailscale-user-login",""),owner))
    if local and not local_authenticated:
        raise HTTPException(401,"Admin token confirmation is required on localhost.")
    if not (local_authenticated or private_remote):
        raise HTTPException(403,"Access requires an authenticated localhost session or configured private owner connection.")
    # Same-origin middleware rejects cross-site origins and DNS-rebinding hosts.
    expires=str(int(time.time())+8*3600)
    signature=hmac.new(KEY,(expires+"|"+str(request.url.hostname)).encode(),hashlib.sha256).hexdigest()
    response=JSONResponse({"ready":True})
    response.set_cookie(COOKIE,expires+"."+signature,httponly=True,samesite="strict",secure=request.url.scheme=="https" or bool(private_remote),max_age=8*3600,path="/")
    return response
