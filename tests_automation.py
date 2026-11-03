"""Approval-state tests for exact, one-use automation requests."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pydantic import ValidationError
from automation_models import AutomationRequest, canonical_payload, payload_digest


class AutomationModelTests(unittest.TestCase):
    def test_request_schema_and_digest_are_exact(self):
        request = AutomationRequest(
            category="windows",
            action="list_processes",
            arguments={"limit": 25},
        )
        canonical = canonical_payload(request)
        self.assertEqual(
            canonical,
            '{"action":"list_processes","arguments":{"limit":25},"category":"windows","risk":"low"}',
        )
        self.assertEqual(payload_digest(request), payload_digest(request))
        changed = request.model_copy(update={"arguments": {"limit": 26}})
        self.assertNotEqual(payload_digest(request), payload_digest(changed))
        with self.assertRaises(ValidationError):
            AutomationRequest(
                category="windows",
                action="arbitrary_shell",
                arguments={"command": "whoami"},
            )


class AutomationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-automation-")
        import control
        control.DB = Path(self.temp.name) / "test.db"
        from automation_store import init
        with control.connect() as db:
            init(db)

    def tearDown(self):
        self.temp.cleanup()

    def test_approval_is_atomic_and_single_use(self):
        from automation_store import approve, create, get
        request = AutomationRequest(
            category="windows", action="list_processes", arguments={"limit": 10}
        )
        created = create(request)
        self.assertEqual(created["status"], "awaiting_approval")
        approved = approve(created["id"], payload_digest(request))
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(get(created["id"])["status"], "approved")
        with self.assertRaises(KeyError):
            approve(created["id"], payload_digest(request))

    def test_expiry_rejection_cancellation_completion_and_failure(self):
        from automation_store import cancel, complete, create, events, expire, fail, list_requests, reject
        request = AutomationRequest(category="browser", action="browser_snapshot", arguments={})
        expired = create(request, clock=lambda: 100.0)
        self.assertEqual(expire(clock=lambda: 401.0), 1)
        self.assertEqual(list_requests(status="expired")[0]["id"], expired["id"])

        rejected = create(request)
        self.assertEqual(reject(rejected["id"])["status"], "rejected")
        cancelled = create(request)
        self.assertEqual(cancel(cancelled["id"])["status"], "cancelled")
        from automation_store import approve
        done = create(request)
        approve(done["id"], payload_digest(request))
        self.assertEqual(complete(done["id"], {"title": "ok"})["status"], "completed")
        broken = create(request)
        approve(broken["id"], payload_digest(request))
        self.assertEqual(fail(broken["id"], "safe error")["status"], "failed")
        self.assertTrue(any(event["kind"] == "failed" for event in events(broken["id"])))

    def test_digest_mismatch_and_concurrent_replay_fail_closed(self):
        import threading
        from automation_store import approve, create
        request = AutomationRequest(category="windows", action="list_processes", arguments={})
        created = create(request)
        with self.assertRaises(KeyError):
            approve(created["id"], "0" * 64)
        outcomes = []
        def consume():
            try:
                approve(created["id"], payload_digest(request))
                outcomes.append("approved")
            except KeyError:
                outcomes.append("rejected")
        threads = [threading.Thread(target=consume) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(outcomes, ["approved", "rejected"])


class AutomationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-automation-api-")
        import control
        control.DB = Path(self.temp.name) / "test.db"
        from control import auth
        from gateway import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth] = lambda: None
        self.app = app
        self.client = TestClient(app, base_url="http://127.0.0.1")
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.app.dependency_overrides.clear()
        self.temp.cleanup()

    def test_request_review_rejection_and_cancellation(self):
        created = self.client.post("/control/automation/requests", json={
            "category": "windows", "action": "list_processes",
            "arguments": {"limit": 20},
        })
        self.assertEqual(created.status_code, 200, created.text)
        request_id = created.json()["id"]
        detail = self.client.get("/control/automation/requests/" + request_id)
        self.assertEqual(detail.json()["arguments"], {"limit": 20})
        self.assertEqual(len(self.client.get("/control/automation/requests").json()), 1)
        rejected = self.client.post("/control/automation/requests/" + request_id + "/reject")
        self.assertEqual(rejected.json()["status"], "rejected")
        second = self.client.post("/control/automation/requests", json={
            "category": "windows", "action": "list_processes", "arguments": {},
        }).json()
        cancelled = self.client.post("/control/automation/requests/" + second["id"] + "/cancel")
        self.assertEqual(cancelled.json()["status"], "cancelled")

    def test_emergency_stop_cancels_pending_automation(self):
        created = self.client.post("/control/automation/requests", json={
            "category": "windows", "action": "list_processes", "arguments": {},
        }).json()
        stopped = self.client.post("/control/stop")
        self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertEqual(stopped.json()["automation_requests"], 1)
        detail = self.client.get("/control/automation/requests/" + created["id"]).json()
        self.assertEqual(detail["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
