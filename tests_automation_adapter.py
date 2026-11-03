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


class BrowserToolTests(unittest.TestCase):
    def test_isolated_browser_policy_and_lifecycle(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from adapter.browser_tools import BrowserTools
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b"""<title>Jarvis Test</title><button id='go' onclick=\"document.querySelector('#status').textContent='clicked'\">Go</button><div id='status'>ready</div><input id='text'><input id='password' type='password'><input id='upload' type='file'><a id='download' href='/file' download>Download</a>"""
                self.send_response(200); self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        with tempfile.TemporaryDirectory(prefix="jarvis-browser-tools-") as directory:
            tools = BrowserTools(Path(directory), {"127.0.0.1"})
            try:
                session = tools.create_session()
                url = f"http://127.0.0.1:{server.server_port}/"
                self.assertEqual(tools.navigate(session["session_id"], url)["title"], "Jarvis Test")
                self.assertIn("ready", tools.snapshot(session["session_id"])["text"])
                tools.fill(session["session_id"], "#text", "hello")
                with self.assertRaises(ValueError):
                    tools.fill(session["session_id"], "#password", "blocked")
                with self.assertRaises(ValueError):
                    tools.click(session["session_id"], selector="#upload")
                with self.assertRaises(ValueError):
                    tools.click(session["session_id"], selector="#download")
                with self.assertRaises(ValueError):
                    tools.navigate(session["session_id"], "https://user:pass@example.com/")
                tools.click(session["session_id"], selector="#go")
                self.assertIn("clicked", tools.snapshot(session["session_id"])["text"])
                shot = tools.screenshot(session["session_id"])
                self.assertTrue(Path(shot["path"]).is_relative_to(Path(directory)))
                self.assertEqual(tools.close_session(session["session_id"])["status"], "closed")
                with self.assertRaises(ValueError):
                    tools.navigate(session["session_id"], "file:///C:/Windows/win.ini")
            finally:
                tools.close()
                server.shutdown(); thread.join(timeout=5); server.server_close()


class AdapterAuthTests(unittest.TestCase):
    def test_mcp_endpoint_requires_startup_secret(self):
        from fastapi.testclient import TestClient
        from adapter.automation_adapter import build_app
        with tempfile.TemporaryDirectory(prefix="jarvis-adapter-auth-") as directory:
            root = Path(directory)
            sleeper = root / "sleeper.py"
            sleeper.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            tools = WindowsTools([root], [Path(sys.executable).resolve()])
            app = build_app(tools, "s" * 32)
            with TestClient(app, base_url="http://127.0.0.1") as client:
                self.assertEqual(client.get("/mcp").status_code, 401)
                self.assertEqual(client.post("/emergency-stop").status_code, 401)
                accepted = client.get(
                    "/mcp", headers={"Authorization": "Bearer " + "s" * 32}
                )
                self.assertNotEqual(accepted.status_code, 401)
                started = tools.start_process(sys.executable, [str(sleeper)])
                process = tools.owned[started["pid"]]
                stopped = client.post(
                    "/emergency-stop",
                    headers={"Authorization": "Bearer " + "s" * 32},
                )
                self.assertEqual(stopped.status_code, 200, stopped.text)
                self.assertIsNotNone(process.poll())
                self.assertFalse(tools.owned)
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
            os.environ["JARVIS_ADMIN_TOKEN"] = "approval-test-token"
            try:
                with TestClient(app, base_url="http://127.0.0.1") as client:
                    def approve(row):
                        return client.post(
                            "/control/automation/requests/" + row["id"] + "/approve",
                            headers={"X-Jarvis-Approval": "approval-test-token"},
                            json={"digest": row["digest"]},
                        )
                    health = client.get("/control/automation/health")
                    self.assertEqual(health.status_code, 200, health.text)
                    self.assertTrue(health.json()["available"])
                    self.assertIn("windows_list_files", health.json()["actions"])
                    created = client.post("/control/automation/requests", json={
                        "category": "windows", "action": "list_files",
                        "arguments": {"path": str(root)},
                    }).json()
                    approved = approve(created)
                    self.assertEqual(approved.status_code, 200, approved.text)
                    self.assertEqual(approved.json()["status"], "completed")
                    self.assertIsInstance(approved.json()["result"], dict)
                    self.assertIn("output", approved.json()["result"])
                    self.assertIn("visible.txt", str(approved.json()["result"]["output"]))
                    process_request = client.post("/control/automation/requests", json={
                        "category": "windows", "action": "list_processes",
                        "arguments": {"limit": 5},
                    }).json()
                    process_result = approve(process_request)
                    self.assertEqual(process_result.status_code, 200, process_result.text)
                    self.assertEqual(process_result.json()["status"], "completed")
                    self.assertIn("pid", str(process_result.json()["result"]))
                    os.environ["JARVIS_AUTOMATION_SECRET"] = "x" * 32
                    failed_request = client.post("/control/automation/requests", json={
                        "category": "windows", "action": "list_processes", "arguments": {},
                    }).json()
                    failed = approve(failed_request)
                    self.assertEqual(failed.status_code, 502, failed.text)
                    failed_detail = client.get(
                        "/control/automation/requests/" + failed_request["id"]
                    ).json()
                    self.assertEqual(failed_detail["status"], "failed")
                    os.environ["JARVIS_AUTOMATION_SECRET"] = secret
                    self.assertEqual(approve(created).status_code, 409)
            finally:
                app.dependency_overrides.clear()
                os.environ.pop("JARVIS_AUTOMATION_URL", None)
                os.environ.pop("JARVIS_AUTOMATION_SECRET", None)
                os.environ["JARVIS_ADMIN_TOKEN"] = "test-only-token"
                server.should_exit = True
                thread.join(timeout=5)
                tools.close()


class BrowserApprovalIntegrationTests(unittest.TestCase):
    def test_approved_browser_sequence_uses_isolated_profile(self):
        import threading, time, uvicorn
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from fastapi.testclient import TestClient
        from adapter.automation_adapter import build_app
        from adapter.browser_tools import BrowserTools
        from control import auth
        import control
        from gateway import app
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body=b"<title>Approved Browser</title><p>browser ready</p>"
                self.send_response(200); self.send_header("Content-Length",str(len(body)))
                self.end_headers(); self.wfile.write(body)
            def log_message(self,*args): pass
        page_server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        page_thread=threading.Thread(target=page_server.serve_forever,daemon=True);page_thread.start()
        secret="b"*32
        with tempfile.TemporaryDirectory(prefix="jarvis-browser-approval-") as directory:
            root=Path(directory);control.DB=root/"test.db"
            windows=WindowsTools([root],[Path(sys.executable).resolve()])
            browser=BrowserTools(root/"shots",{"127.0.0.1"})
            server=uvicorn.Server(uvicorn.Config(build_app(windows,secret,browser),host="127.0.0.1",port=18802,log_level="error"))
            thread=threading.Thread(target=server.run,daemon=True);thread.start()
            for _ in range(50):
                if server.started: break
                time.sleep(.1)
            os.environ["JARVIS_AUTOMATION_URL"]="http://127.0.0.1:18802/mcp"
            os.environ["JARVIS_AUTOMATION_SECRET"]=secret
            app.dependency_overrides[auth]=lambda:None
            os.environ["JARVIS_ADMIN_TOKEN"]="approval-test-token"
            try:
                with TestClient(app,base_url="http://127.0.0.1") as client:
                    def run(action,arguments):
                        row=client.post("/control/automation/requests",json={"category":"browser","action":action,"arguments":arguments}).json()
                        response=client.post("/control/automation/requests/"+row["id"]+"/approve",headers={"X-Jarvis-Approval":"approval-test-token"},json={"digest":row["digest"]})
                        self.assertEqual(response.status_code,200,response.text)
                        return response.json()["result"]["output"]
                    session=run("browser_create",{})["session_id"]
                    url=f"http://127.0.0.1:{page_server.server_port}/"
                    self.assertEqual(run("browser_navigate",{"session_id":session,"url":url})["title"],"Approved Browser")
                    self.assertIn("browser ready",run("browser_snapshot",{"session_id":session})["text"])
                    self.assertEqual(run("browser_close",{"session_id":session})["status"],"closed")
            finally:
                app.dependency_overrides.clear();os.environ.pop("JARVIS_AUTOMATION_URL",None);os.environ.pop("JARVIS_AUTOMATION_SECRET",None);os.environ["JARVIS_ADMIN_TOKEN"]="test-only-token"
                server.should_exit=True;thread.join(timeout=5);browser.close();windows.close()
                page_server.shutdown();page_thread.join(timeout=5);page_server.server_close()


if __name__ == "__main__":
    unittest.main()
