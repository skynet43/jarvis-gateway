"""SQLite state for immutable, one-use automation approvals."""
import json
import secrets
import sqlite3
import time

from automation_models import AutomationRequest, payload_digest
from control import LOCK, connect, now, record


def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automation_requests (
        id TEXT PRIMARY KEY, category TEXT NOT NULL, action TEXT NOT NULL,
        arguments TEXT NOT NULL, risk TEXT NOT NULL, digest TEXT NOT NULL,
        status TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL,
        expires REAL NOT NULL, result TEXT, error TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS automation_events (
        id INTEGER PRIMARY KEY, request_id TEXT NOT NULL, at TEXT NOT NULL,
        kind TEXT NOT NULL, details TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS automation_status_created ON automation_requests(status,created)")


def _event(db, request_id, kind, details=None):
    details = details or {}
    db.execute("INSERT INTO automation_events(request_id,at,kind,details) VALUES(?,?,?,?)",
               (request_id, now(), kind, json.dumps(details, separators=(",", ":"))))
    record(db, "automation." + kind, {"id": request_id, **details})


def _row(row):
    if not row:
        raise KeyError("Automation request not found")
    data = dict(row)
    data["arguments"] = json.loads(data["arguments"])
    if data["result"] is not None:
        data["result"] = json.loads(data["result"])
    return data


def create(request: AutomationRequest, *, clock=time.time):
    request_id = secrets.token_urlsafe(18)
    stamp = now()
    expires = clock() + 300
    with LOCK, connect() as db:
        init(db)
        db.execute("""INSERT INTO automation_requests
            (id,category,action,arguments,risk,digest,status,created,updated,expires)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (request_id, request.category, request.action,
             json.dumps(request.arguments, separators=(",", ":"), sort_keys=True),
             request.risk, payload_digest(request), "awaiting_approval", stamp, stamp, expires))
        _event(db, request_id, "approval_requested",
               {"action": request.action, "risk": request.risk})
    return get(request_id)


def get(request_id):
    with LOCK, connect() as db:
        init(db)
        db.row_factory = sqlite3.Row
        return _row(db.execute("SELECT * FROM automation_requests WHERE id=?", (request_id,)).fetchone())


def approve(request_id, digest, *, clock=time.time):
    with LOCK, connect() as db:
        init(db)
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute("""UPDATE automation_requests SET status='approved',updated=?
            WHERE id=? AND status='awaiting_approval' AND digest=? AND expires>?""",
            (now(), request_id, digest, clock())).rowcount
        if not changed:
            raise KeyError("Request expired, changed, or already consumed")
        _event(db, request_id, "approved")
    return get(request_id)


def list_requests(status=None):
    allowed = {"awaiting_approval", "approved", "rejected", "cancelled", "expired",
               "completed", "failed"}
    if status is not None and status not in allowed:
        raise ValueError("Invalid automation status")
    with LOCK, connect() as db:
        init(db)
        db.row_factory = sqlite3.Row
        sql = "SELECT * FROM automation_requests"
        params = ()
        if status:
            sql += " WHERE status=?"
            params = (status,)
        sql += " ORDER BY created DESC LIMIT 100"
        return [_row(row) for row in db.execute(sql, params)]


def events(request_id):
    with LOCK, connect() as db:
        init(db)
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            "SELECT * FROM automation_events WHERE request_id=? ORDER BY id LIMIT 200",
            (request_id,))]


def _transition(request_id, expected, target, kind, *, result=None, error=None):
    encoded = None if result is None else json.dumps(result, separators=(",", ":"))
    if encoded and len(encoded.encode("utf-8")) > 65536:
        raise ValueError("Automation result too large")
    if error is not None:
        error = str(error)[:500]
    with LOCK, connect() as db:
        init(db)
        changed = db.execute("""UPDATE automation_requests
            SET status=?,updated=?,result=?,error=? WHERE id=? AND status=?""",
            (target, now(), encoded, error, request_id, expected)).rowcount
        if not changed:
            raise KeyError("Automation request is not in the expected state")
        _event(db, request_id, kind)
    return get(request_id)


def reject(request_id):
    return _transition(request_id, "awaiting_approval", "rejected", "rejected")


def cancel(request_id):
    for expected in ("awaiting_approval", "approved"):
        try:
            return _transition(request_id, expected, "cancelled", "cancelled")
        except KeyError:
            pass
    raise KeyError("Automation request is not cancellable")


def complete(request_id, result):
    return _transition(request_id, "approved", "completed", "completed", result=result)


def fail(request_id, error):
    return _transition(request_id, "approved", "failed", "failed", error=error)


def expire(*, clock=time.time):
    with LOCK, connect() as db:
        init(db)
        ids = [row[0] for row in db.execute(
            "SELECT id FROM automation_requests WHERE status='awaiting_approval' AND expires<=?",
            (clock(),))]
        for request_id in ids:
            db.execute("UPDATE automation_requests SET status='expired',updated=? WHERE id=?",
                       (now(), request_id))
            _event(db, request_id, "expired")
        return len(ids)


def cancel_all(db):
    init(db)
    ids = [row[0] for row in db.execute(
        "SELECT id FROM automation_requests WHERE status IN ('awaiting_approval','approved')"
    )]
    for request_id in ids:
        db.execute("UPDATE automation_requests SET status='cancelled',updated=? WHERE id=?",
                   (now(), request_id))
        _event(db, request_id, "cancelled", {"emergency_stop": True})
    return ids
