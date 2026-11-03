"""Authenticated loopback MCP server for approved Windows automation."""
import atexit
import hmac
import os
from pathlib import Path

import uvicorn
from mcp.server import MCPServer

from adapter.browser_tools import BrowserTools
from adapter.windows_tools import WindowsTools


class StartupSecretMiddleware:
    def __init__(self, app, secret):
        if len(secret) < 32:
            raise ValueError("Automation startup secret must be at least 32 characters")
        self.app = app
        self.expected = ("Bearer " + secret).encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self.expected):
                await send({
                    "type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({"type": "http.response.body", "body": b'{"detail":"Unauthorized"}'})
                return
        await self.app(scope, receive, send)


def build_app(tools, secret, browser=None):
    server = MCPServer("jarvis-automation")

    @server.tool()
    def windows_list_files(path: str):
        return tools.list_files(path)

    @server.tool()
    def windows_file_metadata(path: str):
        return tools.file_metadata(path)

    @server.tool()
    def windows_read_text(path: str):
        return tools.read_text(path)

    @server.tool()
    def windows_list_processes(limit: int = 100):
        return tools.list_processes(limit)

    @server.tool()
    def windows_start_process(executable: str, arguments: list[str]):
        return tools.start_process(executable, arguments)

    @server.tool()
    def windows_stop_process(pid: int):
        return tools.stop_process(pid)

    if browser:
        @server.tool()
        def browser_create():
            return browser.create_session()
        @server.tool()
        def browser_close(session_id: str):
            return browser.close_session(session_id)
        @server.tool()
        def browser_navigate(session_id: str, url: str):
            return browser.navigate(session_id, url)
        @server.tool()
        def browser_snapshot(session_id: str):
            return browser.snapshot(session_id)
        @server.tool()
        def browser_click(session_id: str, selector: str | None = None,
                          role: str | None = None, name: str | None = None):
            return browser.click(session_id, selector=selector, role=role, name=name)
        @server.tool()
        def browser_fill(session_id: str, selector: str, text: str):
            return browser.fill(session_id, selector, text)
        @server.tool()
        def browser_screenshot(session_id: str):
            return browser.screenshot(session_id)

    return StartupSecretMiddleware(
        server.streamable_http_app(stateless_http=True), secret
    )


def configured_app():
    secret = os.environ.get("JARVIS_AUTOMATION_SECRET", "")
    roots = [Path(value) for value in os.environ.get("JARVIS_AUTOMATION_ROOTS", "").split(os.pathsep) if value]
    executables = [Path(value) for value in os.environ.get("JARVIS_AUTOMATION_EXECUTABLES", "").split(os.pathsep) if value]
    output = Path(os.environ.get("JARVIS_BROWSER_OUTPUT", str(Path.cwd() / "work" / "browser-output")))
    hosts = {value.strip().lower() for value in os.environ.get(
        "JARVIS_BROWSER_HOSTS", "127.0.0.1,localhost").split(",") if value.strip()}
    browser = BrowserTools(output, hosts)
    atexit.register(browser.close)
    return build_app(WindowsTools(roots, executables), secret, browser)


if __name__ == "__main__":
    uvicorn.run(
        configured_app(), host="127.0.0.1",
        port=int(os.environ.get("JARVIS_AUTOMATION_PORT", "18798")),
        log_level="warning",
    )
