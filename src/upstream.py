"""Bounded upstream readers shared by inference and model discovery."""
import json
async def bounded_json(response,limit=1048576):
    response.raise_for_status()
    body=bytearray()
    async for chunk in response.aiter_bytes():
        if len(body)+len(chunk)>limit:
            raise ValueError("Upstream response exceeded limit")
        body.extend(chunk)
    return json.loads(body)
async def bounded_lines(response,limit=262144,total_limit=1048576):
    response.raise_for_status()
    pending=bytearray()
    total=0
    async for chunk in response.aiter_bytes():
        total+=len(chunk)
        if total>total_limit:
            raise ValueError("Upstream stream exceeded limit")
        pending.extend(chunk)
        while b"\n" in pending:
            line,_,rest=pending.partition(b"\n")
            pending=bytearray(rest)
            if len(line)>limit:raise ValueError("Upstream line exceeded limit")
            yield line.decode("utf-8")
        if len(pending)>limit:raise ValueError("Upstream line exceeded limit")
    if pending:yield pending.decode("utf-8")
