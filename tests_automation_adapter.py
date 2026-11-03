"""Security tests for the loopback Windows automation adapter."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from adapter.windows_tools import WindowsTools


class WindowsToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-windows-tools-")
        self.root = Path(self.temp.name).resolve()
        (self.root / "safe.txt").write_text("hello", encoding="utf-8")
        (self.root / "secret-token.txt").write_text("blocked", encoding="utf-8")
        (self.root / "sleeper.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        self.tools = WindowsTools([self.root], [Path(sys.executable).resolve()])

    def tearDown(self):
        self.tools.close()
        self.temp.cleanup()

    def test_files_stay_inside_roots_and_sensitive_names_are_blocked(self):
        self.assertIn("safe.txt", self.tools.list_files(str(self.root)))
        self.assertEqual(self.tools.read_text(str(self.root / "safe.txt"))["content"], "hello")
        with self.assertRaises(ValueError):
            self.tools.read_text(str(self.root.parent / "outside.txt"))
        with self.assertRaises(ValueError):
            self.tools.read_text(str(self.root / "secret-token.txt"))

    def test_only_owned_allowlisted_processes_can_be_stopped(self):
        with self.assertRaises(ValueError):
            self.tools.start_process("cmd.exe", ["/c", "echo", "unsafe"])
        with self.assertRaises(ValueError):
            self.tools.start_process(sys.executable, ["unsafe&argument"])
        started = self.tools.start_process(
            sys.executable, [str(self.root / "sleeper.py")]
        )
        self.assertGreater(started["pid"], 0)
        stopped = self.tools.stop_process(started["pid"])
        self.assertEqual(stopped["status"], "stopped")
        with self.assertRaises(ValueError):
            self.tools.stop_process(started["pid"])


class AdapterAuthTests(unittest.TestCase):
    def test_mcp_endpoint_requires_startup_secret(self):
        from fastapi.testclient import TestClient
        from adapter.automation_adapter import build_app
        with tempfile.TemporaryDirectory(prefix="jarvis-adapter-auth-") as directory:
            tools = WindowsTools([Path(directory)], [Path(sys.executable).resolve()])
            app = build_app(tools, "s" * 32)
            with TestClient(app, base_url="http://127.0.0.1") as client:
                self.assertEqual(client.get("/mcp").status_code, 401)
                accepted = client.get(
                    "/mcp", headers={"Authorization": "Bearer " + "s" * 32}
                )
                self.assertNotEqual(accepted.status_code, 401)
            tools.close()


class AdapterIntegrationTests(unittest.TestCase):
    def test_approved_request_executes_once_against_real_adapter(self):
        import threading
        import time
        import uvicorn
        from fastapi.testclient import TestClient
        from adapter.automation_adapter import build_app
        from control import auth
        import control
        from gateway import app
        secret = "i" * 32
        with tempfile.TemporaryDirectory(prefix="jarvis-adapter-integration-") as directory:
            root = Path(directory)
            (root / "visible.txt").write_text("ready", encoding="utf-8")
            control.DB = root / "test.db"
            tools = WindowsTools([root], [Path(sys.executable).resolve()])
            server = uvicorn.Server(uvicorn.Config(
                build_app(tools, secret), host="127.0.0.1", port=18800, log_level="error"
            ))
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            for _ in range(50):
                if server.started:
                    break
                time.sleep(0.1)
            self.assertTrue(server.started)
            os.environ["JARVIS_AUTOMATION_URL"] = "http://127.0.0.1:18800/mcp"
            os.environ["JARVIS_AUTOMATION_SECRET"] = secret
            app.dependency_overrides[auth] = lambda: None
            try:
                with TestClient(app, base_url="http://127.0.0.1") as client:
                    health = client.get("/control/automation/health")
                    self.assertEqual(health.status_code, 200, health.text)
                    self.assertTrue(health.json()["available"])
                    self.assertIn("windows_list_files", health.json()["actions"])
                    created = client.post("/control/automation/requests", json={
                        "category": "windows", "action": "list_files",
                        "arguments": {"path": str(root)},
                    }).json()
                    approved = client.post(
                        "/control/automation/requests/" + created["id"] + "/approve"
                    )
                    self.assertEqual(approved.status_code, 200, approved.text)
                    self.assertEqual(approved.json()["status"], "completed")
                    self.assertIsInstance(approved.json()["result"], dict)
                    self.assertIn("visible.txt", str(approved.json()["result"]))
                    process_request = client.post("/control/automation/requests", json={
                        "category": "windows", "action": "list_processes",
                        "arguments": {"limit": 5},
                    }).json()
                    process_result = client.post(
                        "/control/automation/requests/" + process_request["id"] + "/approve"
                    )
                    self.assertEqual(process_result.status_code, 200, process_result.text)
                    self.assertEqual(process_result.json()["status"], "completed")
                    self.assertIn("pid", str(process_result.json()["result"]))
                    os.environ["JARVIS_AUTOMATION_SECRET"] = "x" * 32
                    failed_request = client.post("/control/automation/requests", json={
                        "category": "windows", "action": "list_processes", "arguments": {},
                    }).json()
                    failed = client.post(
                        "/control/automation/requests/" + failed_request["id"] + "/approve"
                    )
                    self.assertEqual(failed.status_code, 502, failed.text)
                    failed_detail = client.get(
                        "/control/automation/requests/" + failed_request["id"]
                    ).json()
                    self.assertEqual(failed_detail["status"], "failed")
                    os.environ["JARVIS_AUTOMATION_SECRET"] = secret
                    self.assertEqual(client.post(
                        "/control/automation/requests/" + created["id"] + "/approve"
                    ).status_code, 409)
            finally:
                app.dependency_overrides.clear()
                os.environ.pop("JARVIS_AUTOMATION_URL", None)
                os.environ.pop("JARVIS_AUTOMATION_SECRET", None)
                server.should_exit = True
                thread.join(timeout=5)
                tools.close()


if __name__ == "__main__":
    unittest.main()
