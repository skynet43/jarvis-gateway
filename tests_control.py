import os, sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ["JARVIS_ADMIN_TOKEN"] = "test-only-token"
from fastapi.testclient import TestClient
from gateway import app
class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import control
        cls.original_db=control.DB
        cls.tmp=tempfile.TemporaryDirectory()
        control.DB=Path(cls.tmp.name)/"original-regression.db"
    @classmethod
    def tearDownClass(cls):
        import control
        control.DB=cls.original_db
        cls.tmp.cleanup()
    def setUp(self):
        self.c = TestClient(app, base_url="http://127.0.0.1")
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
    def test_fresh_install_starts_blank_and_adds_selected_agent(self):
        import control
        original=control.DB
        old=os.environ.pop("JARVIS_TEST_TEMPLATES",None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                control.DB=Path(directory)/"fresh.db"
                self.assertEqual(self.c.get("/control/agents",headers=self.h).json(),[])
                response=self.c.post("/control/agents/setup",headers=self.h,json={"templates":["rosie"]})
                self.assertEqual(response.status_code,200)
                self.assertEqual([a["id"] for a in response.json()],["rosie"])
                self.assertEqual(self.c.post("/control/jobs",headers=self.h,json={"agent":"benson","prompt":"No"}).status_code,404)
        finally:
            control.DB=original
            if old is not None:os.environ["JARVIS_TEST_TEMPLATES"]=old
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
