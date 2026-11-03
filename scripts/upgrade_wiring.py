from pathlib import Path
root=Path(__file__).resolve().parent.parent
p=root/'src/gateway.py'
s=p.read_text()
s=s.replace('app.include_router(control_router)','app.include_router(control_router)\nfrom harness import router as harness_router\napp.include_router(harness_router)')
s=s.replace('stop,thread=start()','stop,thread=start()\n    from harness import start as start_harness\n    harness_stop,harness_thread=start_harness()')
s=s.replace('stop.set()\n        await asyncio.to_thread(thread.join,10)','stop.set()\n        harness_stop.set()\n        await asyncio.to_thread(thread.join,10)\n        await asyncio.to_thread(harness_thread.join,10)')
s=s.replace('if host not in ("127.0.0.1","localhost","::1"):','remote_origin=os.environ.get("JARVIS_HTTPS_ORIGIN","").rstrip("/")\n    remote_host=urlsplit(remote_origin).hostname if remote_origin.startswith("https://") else None\n    if host not in ("127.0.0.1","localhost","::1",remote_host):')
s=s.replace('if origin and origin != str(request.base_url).rstrip("/"):','allowed_origins={str(request.base_url).rstrip("/")}\n    if remote_origin and host==remote_host:\n        allowed_origins.add(remote_origin)\n    if origin and origin not in allowed_origins:')
p.write_text(s)
p=root/'src/control.py'
s=p.read_text().replace('(status,status,"%"+q+"%",limit,offset)','(status or None,status or None,"%"+q+"%",limit,offset)')
p.write_text(s)
p=root/'frontend/src/main.tsx'
s=p.read_text().replace("useState('codex')","useState('ollama-tools')")
s=s.replace('Read-only sandbox. Explicit workspace allowlist. Each session requires approval. Runtime outputs are untrusted text.','Allowlisted source-file reads only. No shell or write tools. Each session requires approval. File contents and runtime outputs are untrusted text.')
s=s.replace('Its configured provider may receive prompt and workspace content.','The local Ollama model receives the prompt and approved source-file contents.')
p.write_text(s)
p=root/'frontend/src/style.css'
p.write_text(p.read_text().replace('@import url();\n',''))
p=root/'tests_control.py'
s=p.read_text().replace('self.c = TestClient(app)','self.c = TestClient(app, base_url="http://127.0.0.1")')
p.write_text(s)
