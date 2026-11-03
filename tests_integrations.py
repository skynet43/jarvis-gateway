"""Integration checks for local provider and MCP approval paths."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"src"))
_test_db_dir=tempfile.TemporaryDirectory(prefix="jarvis-mcp-test-")
os.environ["JARVIS_DB"]=str(Path(_test_db_dir.name)/"test.db")
import threading
import time
import unittest
import uvicorn
from mcp.server import MCPServer
from fastapi.testclient import TestClient
from providers import Connection, endpoint_for
from gateway import app

class IntegrationTests(unittest.TestCase):
    def test_provider_endpoint_restrictions(self):
        self.assertEqual(endpoint_for(Connection(provider="lm-studio")),"http://127.0.0.1:1234/v1")
        for url in ("http://192.168.1.1:1234/v1","http://127.0.0.1:1234@evil.example/v1","http://127.0.0.1:1234/v1?x=1"):
            with self.assertRaises(Exception):endpoint_for(Connection(provider="custom-local",endpoint=url))

    def test_real_mcp_tool_requires_approval(self):
        server=MCPServer("jarvis-acceptance")
        calls=[]
        @server.tool()
        def echo(message:str)->str:
            calls.append(message)
            return message
        config=uvicorn.Config(server.streamable_http_app(stateless_http=True),host="127.0.0.1",port=18799,log_level="error")
        runtime=uvicorn.Server(config)
        thread=threading.Thread(target=runtime.run,daemon=True)
        thread.start()
        for _ in range(50):
            if runtime.started:break
            time.sleep(.1)
        self.assertTrue(runtime.started)
        from mcp_bridge import SERVERS,PENDING
        SERVERS.clear();PENDING.clear()
        try:
            from control import auth
            app.dependency_overrides[auth]=lambda:None
            try:
                    with TestClient(app,base_url="http://127.0.0.1") as client:
                        added=client.post("/control/mcp/servers",json={"name":"Echo","url":"http://127.0.0.1:18799/mcp"})
                        self.assertEqual(added.status_code,200,added.text)
                        sid=added.json()["id"]
                        self.assertIn("echo",[x["name"] for x in added.json()["tools"]])
                        requested=client.post("/control/mcp/requests",json={"server_id":sid,"tool":"echo","arguments":{"message":"READY"}})
                        self.assertEqual(requested.status_code,200,requested.text)
                        self.assertEqual(calls,[])
                        rid=requested.json()["id"]
                        done=client.post("/control/mcp/requests/"+rid+"/approve")
                        self.assertEqual(done.status_code,200,done.text)
                        self.assertEqual(calls,["READY"])
                        self.assertEqual(client.post("/control/mcp/requests/"+rid+"/approve").status_code,404)
            finally:app.dependency_overrides.clear()
        finally:
            runtime.should_exit=True
            thread.join(timeout=5)

if __name__=="__main__":unittest.main()
