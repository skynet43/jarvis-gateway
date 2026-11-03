"""Synchronous, bounded bridge to an isolated Playwright worker."""
import json
import os
import queue
import shutil
import subprocess
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit


class BrowserTools:
    def __init__(self, output_root, allowed_hosts):
        self.output_root = Path(output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.allowed_hosts = {str(host).lower() for host in allowed_hosts}
        if not self.allowed_hosts:
            raise ValueError("At least one browser host is required")
        node = shutil.which("node")
        if not node:
            raise ValueError("Node.js is required for browser automation")
        worker = Path(__file__).with_name("browser_worker.mjs")
        env = os.environ.copy()
        env["JARVIS_BROWSER_OUTPUT"] = str(self.output_root)
        env["JARVIS_BROWSER_HOSTS"] = ",".join(sorted(self.allowed_hosts))
        self.process = subprocess.Popen(
            [node, str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
            env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.responses = queue.Queue()
        self.lock = threading.Lock()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        for line in self.process.stdout:
            try:
                self.responses.put(json.loads(line))
            except json.JSONDecodeError:
                continue

    def _call(self, action, arguments=None, timeout=30):
        if self.process.poll() is not None:
            raise ValueError("Browser worker is unavailable")
        message_id = uuid.uuid4().hex
        with self.lock:
            self.process.stdin.write(json.dumps({
                "id": message_id, "action": action, "arguments": arguments or {},
            }, separators=(",", ":")) + "\n")
            self.process.stdin.flush()
            try:
                response = self.responses.get(timeout=timeout)
            except queue.Empty:
                raise ValueError("Browser action timed out") from None
            if response.get("id") != message_id:
                raise ValueError("Browser worker response mismatch")
            if not response.get("ok"):
                raise ValueError(response.get("error", "Browser action failed"))
            return response["result"]

    def create_session(self):
        return self._call("create_session", timeout=45)

    def navigate(self, session_id, url):
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or parsed.username or parsed.password
                or (parsed.hostname or "").lower() not in self.allowed_hosts):
            raise ValueError("Browser URL is not allowed")
        return self._call("navigate", {"session_id": session_id, "url": url})

    def snapshot(self, session_id):
        return self._call("snapshot", {"session_id": session_id})

    def click(self, session_id, *, selector=None, role=None, name=None):
        return self._call("click", {
            "session_id": session_id, "selector": selector,
            "role": role, "name": name,
        })

    def fill(self, session_id, selector, text):
        return self._call("fill", {
            "session_id": session_id, "selector": selector, "text": text,
        })

    def screenshot(self, session_id):
        result = self._call("screenshot", {"session_id": session_id})
        target = Path(result["path"]).resolve(strict=True)
        if not target.is_relative_to(self.output_root):
            raise ValueError("Screenshot left approved output root")
        return result

    def close_session(self, session_id):
        return self._call("close_session", {"session_id": session_id})

    def close(self):
        if self.process.poll() is None:
            try:
                self._call("shutdown", timeout=10)
            except (OSError, ValueError):
                pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream:
                stream.close()
