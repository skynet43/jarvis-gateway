"""Isolated acceptance server; never uses the user's database or admin token."""
import os, secrets, sys, tempfile, threading, time
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(root),str(root/'src')]
if not os.environ.get('JARVIS_ACCEPTANCE_TOKEN'):
 raise SystemExit('Acceptance token must be supplied by the test runner')
os.environ['JARVIS_ADMIN_TOKEN']=os.environ['JARVIS_ACCEPTANCE_TOKEN']
os.environ['JARVIS_TEST_TEMPLATES']='1'
with tempfile.TemporaryDirectory(prefix='jarvis-browser-') as directory:
 os.environ['JARVIS_DB']=str(Path(directory)/'test.db')
 os.environ['JARVIS_AUTOMATION_SECRET']=secrets.token_urlsafe(32)
 adapter_port=int(os.environ.get('JARVIS_BROWSER_TEST_ADAPTER_PORT','18803'))
 gateway_port=int(os.environ.get('JARVIS_BROWSER_TEST_PORT','8766'))
 os.environ['JARVIS_AUTOMATION_URL']=f'http://127.0.0.1:{adapter_port}/mcp'
 import uvicorn
 from adapter.automation_adapter import build_app
 from adapter.browser_tools import BrowserTools
 from adapter.windows_tools import WindowsTools
 browser=BrowserTools(Path(directory)/'screenshots',{'127.0.0.1'})
 windows=WindowsTools([Path(directory)],[Path(sys.executable).resolve()])
 adapter=uvicorn.Server(uvicorn.Config(
  build_app(windows,os.environ['JARVIS_AUTOMATION_SECRET'],browser),
  host='127.0.0.1',port=adapter_port,log_level='error'))
 thread=threading.Thread(target=adapter.run,daemon=True)
 thread.start()
 for _ in range(50):
  if adapter.started:break
  time.sleep(.1)
 if not adapter.started:raise SystemExit('Automation adapter did not start')
 try:
  uvicorn.run('gateway:app',host='127.0.0.1',port=gateway_port,log_level='warning')
 finally:
  adapter.should_exit=True
  thread.join(timeout=5)
  browser.close()
  windows.close()
