import asyncio
import concurrent.futures
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'src'))
os.environ['JARVIS_ADMIN_TOKEN']='test-only-token'
import control
import gateway
import worker
import harness
from fastapi.testclient import TestClient
class HardeningTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.original=control.DB
  control.DB=Path(self.tmp.name)/'test.db'
  gateway.buckets.clear()
  self.c=TestClient(gateway.app,base_url='http://127.0.0.1')
  self.h={'X-Jarvis-Token':'test-only-token'}
 def tearDown(self):
  self.c.close()
  control.DB=self.original
  self.tmp.cleanup()
 def job(self):
  return control.submit(control.JobRequest(agent='rosie',prompt='test'))
 def test_privileged_auth_matrix(self):
  for path in ['/control/agents','/control/jobs','/control/audit','/control/models','/control/telemetry','/control/summary','/control/runtimes','/control/sessions','/ollama/models']:
   for h in ({},{'X-Jarvis-Token':'invalid'}):
    self.assertEqual(self.c.get(path,headers=h).status_code,401,path)
  self.assertEqual(self.c.post('/ollama/chat',json={'message':'x'}).status_code,401)
 def test_unicode_token_is_rejected_without_server_error(self):
  with patch.dict(os.environ,{'JARVIS_ADMIN_TOKEN':'secret-☃'}):
   self.assertEqual(self.c.get('/control/agents',headers=self.h).status_code,401)
 def test_host_and_origin(self):
  self.assertEqual(self.c.get('/health',headers={'Host':'evil.example'}).status_code,400)
  self.assertEqual(self.c.get('/control/jobs',headers={**self.h,'Origin':'https://evil.example'}).status_code,403)
  self.assertEqual(self.c.get('/control/jobs',headers={**self.h,'Sec-Fetch-Site':'cross-site'}).status_code,403)
 def test_https_allowlist(self):
  with patch.dict(os.environ,{'JARVIS_HTTPS_ORIGIN':'https://laptop.test.ts.net'}):
   self.assertEqual(self.c.get('/control/jobs',headers={**self.h,'Host':'laptop.test.ts.net','Origin':'https://laptop.test.ts.net'}).status_code,200)
 def test_private_tailscale_browser_session_requires_owner_identity(self):
  with patch.dict(os.environ,{'JARVIS_HTTPS_ORIGIN':'https://laptop.test.ts.net','JARVIS_TAILSCALE_LOGIN':'owner@example.test'}):
   with TestClient(gateway.app,base_url='http://laptop.test.ts.net',client=('100.71.85.13',12345)) as remote:
    self.assertEqual(remote.post('/control/browser-session').status_code,403)
    self.assertEqual(remote.post('/control/browser-session',headers={'Tailscale-User-Login':'other@example.test'}).status_code,403)
    accepted=remote.post('/control/browser-session',headers={'Tailscale-User-Login':'owner@example.test'})
    self.assertEqual(accepted.status_code,200)
    self.assertIn('Secure',accepted.headers['set-cookie'])
   with TestClient(gateway.app,base_url='http://laptop.test.ts.net',client=('192.168.1.10',12345)) as lan:
    self.assertEqual(lan.post('/control/browser-session',headers={'Tailscale-User-Login':'owner@example.test'}).status_code,403)
 def test_payload_limits(self):
  for prompt in ['','   ','x'*8001]:
   self.assertEqual(self.c.post('/control/jobs',headers=self.h,json={'agent':'rosie','prompt':prompt}).status_code,422)
  self.assertEqual(self.c.post('/control/jobs',headers=self.h,content='x'*65537).status_code,413)
 def test_detail_filter_pagination(self):
  j=self.job()
  self.assertEqual(self.c.get('/control/jobs/'+j['id'],headers=self.h).json()['prompt'],'test')
  self.assertEqual(len(self.c.get('/control/jobs?status=&limit=1',headers=self.h).json()),1)
  self.assertEqual(self.c.get('/control/jobs/missing',headers=self.h).status_code,404)
  self.assertEqual(self.c.get('/control/jobs?limit=999',headers=self.h).status_code,422)
 def test_concurrent_submission(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
   jobs=list(pool.map(lambda _:self.job(),range(16)))
  self.assertEqual(len({j['id'] for j in jobs}),16)
 def test_queue_limit(self):
  for _ in range(50):self.job()
  self.assertEqual(self.c.post('/control/jobs',headers=self.h,json={'agent':'rosie','prompt':'overflow'}).status_code,429)
 def test_queued_cancel(self):
  j=self.job()
  self.assertEqual(control.cancel(j['id'])['status'],'cancelled')
  self.assertFalse(asyncio.run(worker.process_one()))
 def test_completed_result_persists(self):
  j=self.job()
  async def answer(*_):return '<script>alert(1)</script> safe text'
  with patch.object(worker,'infer',answer):asyncio.run(worker.process_one())
  self.assertEqual(control.detail(j['id'])['status'],'completed')
  self.assertIn('<script>',control.detail(j['id'])['result'])
  self.assertEqual(self.c.post('/control/jobs/'+j['id']+'/cancel',headers=self.h).status_code,409)
 def test_blocked_stream_cancel_ack(self):
  j=self.job()
  closed=[]
  async def blocked(*_):
   try:await asyncio.sleep(60)
   finally:closed.append(True)
  async def scenario():
   task=asyncio.create_task(worker.process_one())
   await asyncio.sleep(.05)
   self.assertEqual(control.cancel(j['id'])['status'],'cancelling')
   await asyncio.wait_for(task,1)
  with patch.object(worker,'infer',blocked):asyncio.run(scenario())
  self.assertEqual(closed,[True])
  self.assertEqual(control.detail(j['id'])['status'],'cancelled')
  self.assertIsNotNone(control.detail(j['id'])['stream_closed'])
 def test_cancellation_race(self):
  j=self.job()
  async def answer(*_):
   control.cancel(j['id'])
   return 'must not persist'
  with patch.object(worker,'infer',answer):asyncio.run(worker.process_one())
  self.assertEqual(control.detail(j['id'])['status'],'cancelled')
  self.assertIsNone(control.detail(j['id'])['result'])
 def test_failure_and_timeout(self):
  for error in [ValueError('sensitive internal message'),TimeoutError()]:
   j=self.job()
   async def fail(*_):raise error
   with patch.object(worker,'infer',fail):asyncio.run(worker.process_one())
   result=control.detail(j['id'])
   self.assertEqual(result['status'],'failed')
   self.assertNotIn('sensitive',result['error'])
 def test_recovery(self):
  j=self.job()
  worker.claim()
  worker.recover()
  self.assertEqual(control.detail(j['id'])['status'],'failed')
 def test_shutdown_closes_request(self):
  import threading
  j=self.job();stop=threading.Event()
  async def blocked(*_):await asyncio.sleep(60)
  async def scenario():
   task=asyncio.create_task(worker.process_one(stop))
   await asyncio.sleep(.05);stop.set()
   await asyncio.wait_for(task,1)
  with patch.object(worker,'infer',blocked):asyncio.run(scenario())
  self.assertEqual(control.detail(j['id'])['status'],'failed')
 def test_runtime_approval_required(self):
  req={'runtime':'ollama-tools','root':str(harness.ROOT),'prompt':'Review README'}
  sid=self.c.post('/control/sessions',headers=self.h,json=req).json()['id']
  self.assertEqual(harness.sessions()[0]['status'],'awaiting_approval')
  self.assertEqual(self.c.post('/control/sessions/'+sid+'/approve',headers=self.h).status_code,200)
  self.assertEqual(self.c.post('/control/sessions/'+sid+'/approve',headers=self.h).status_code,409)
 def test_runtime_reject_and_invalid_root(self):
  self.assertEqual(self.c.post('/control/sessions',headers=self.h,json={'runtime':'ollama-tools','root':'C:/Windows','prompt':'x'}).status_code,403)
  r=harness.create(harness.SessionRequest(runtime='ollama-tools',root=str(harness.ROOT),prompt='x'))
  harness.reject(r['id'])
  self.assertEqual(harness.sessions()[0]['status'],'rejected')
 def test_tools_deny_escape_private_shell(self):
  for path in ['../outside','data/jarvis.db','.env','.git/config','C:/Windows/win.ini']:
   with self.assertRaises(ValueError):harness.tool(str(harness.ROOT),'read_workspace_file',{'path':path})
  with self.assertRaises(ValueError):harness.tool(str(harness.ROOT),'shell',{'path':'README.md'})
  self.assertIn('Jarvis',harness.tool(str(harness.ROOT),'read_workspace_file',{'path':'README.md'}))
 def test_runtime_lifecycle(self):
  import threading
  s=harness.create(harness.SessionRequest(runtime='ollama-tools',root=str(harness.ROOT),prompt='x'))
  harness.approve(s['id'])
  async def run(*_):return 'Verified test result'
  with patch.object(harness,'run_agent',run):asyncio.run(harness.process_session(threading.Event()))
  self.assertEqual(harness.sessions()[0]['status'],'completed')
  self.assertEqual(harness.sessions()[0]['result'],'Verified test result')
 def test_openapi_contract(self):
  schema=self.c.get('/openapi.json').json()
  self.assertIn('Job',schema['components']['schemas'])
  self.assertIn('/control/sessions/{sid}/approve',schema['paths'])
 def test_security_headers(self):
  r=self.c.get('/dashboard')
  self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy'])
  self.assertEqual(r.headers['cache-control'],'no-store')
 def test_emergency_stop_includes_runtime_sessions(self):
  self.job()
  session=harness.create(harness.SessionRequest(runtime='ollama-tools',root=str(harness.ROOT),prompt='review'))
  harness.approve(session['id'])
  result=control.stop_all()
  self.assertEqual(result['persona_tasks'],1)
  self.assertEqual(result['runtime_sessions'],1)
  self.assertEqual(harness.sessions()[0]['status'],'cancelled')
 def test_event_reconnect_does_not_skip_large_backlog(self):
  with control.LOCK,control.connect() as db:
   for i in range(600):control.record(db,'test.event',{'n':i})
  class Request:
   headers={}
   async def is_disconnected(self):return False
  async def scenario():
   response=await gateway.events(Request(),after=0)
   generator=response.body_iterator
   first=await anext(generator)
   second=await anext(generator)
   await generator.aclose()
   return first,second
  first,second=asyncio.run(scenario())
  self.assertTrue(first.startswith('id: 1'))
  self.assertTrue(second.startswith('id: 2'))
 def test_bounded_upstream_rejects_oversize(self):
  import httpx
  from upstream import bounded_json,bounded_lines
  async def scenario():
   response=httpx.Response(200,content=b'x'*100,request=httpx.Request('GET','http://localhost'))
   with self.assertRaises(ValueError):await bounded_json(response,10)
   response=httpx.Response(200,content=b'x'*100,request=httpx.Request('GET','http://localhost'))
   with self.assertRaises(ValueError):
    async for _ in bounded_lines(response,limit=10):pass
  asyncio.run(scenario())
if __name__=='__main__':unittest.main(verbosity=2)
