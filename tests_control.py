import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ["JARVIS_ADMIN_TOKEN"] = "test-only-token"
from fastapi.testclient import TestClient
from gateway import app
class ControlTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app)
        self.h = {"X-Jarvis-Token": "test-only-token"}
    def test_health(self):
        self.assertEqual(self.c.get("/health").status_code, 200)
    def test_dashboard(self):
        self.assertEqual(self.c.get("/dashboard").status_code, 200)
    def test_auth_required(self):
        self.assertEqual(self.c.get("/control/agents").status_code, 401)
    def test_wrong_auth(self):
        self.assertEqual(self.c.get("/control/agents", headers={"X-Jarvis-Token":"wrong"}).status_code, 401)
    def test_agents(self):
        r=self.c.get("/control/agents", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()),3)
    def test_create_cancel_audit(self):
        r=self.c.post("/control/jobs", headers=self.h,json={"agent":"rosie","prompt":"test"})
        self.assertEqual(r.status_code, 200)
        job=r.json()
        self.assertEqual(job["status"],"queued")
        self.assertTrue(any(j["id"]==job["id"] for j in self.c.get("/control/jobs",headers=self.h).json()))
        r=self.c.post("/control/jobs/"+job["id"]+"/cancel",headers=self.h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()["status"],"cancelled")
        self.assertTrue(any(a["action"]=="job.cancelled" for a in self.c.get("/control/audit",headers=self.h).json()))
    def test_invalid_agent(self):
        self.assertEqual(self.c.post("/control/jobs",headers=self.h,json={"agent":"unknown","prompt":"test"}).status_code,404)
if __name__ == "__main__":
    unittest.main(verbosity=2)
