"""Repeated real-model cancellation measurements; never equate GPU load with unload."""
import json,os,subprocess,time
from pathlib import Path
import requests
BASE=os.environ.get('JARVIS_BASE_URL','http://127.0.0.1:8767')
HEADERS={'X-Jarvis-Token':os.environ['JARVIS_ADMIN_TOKEN']}
def get(path):return requests.get(BASE+'/control/'+path,headers=HEADERS,timeout=10).json()
def gpu():
 try:
  r=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4)
  values=r.stdout.strip().splitlines()[0].split(',')
  return {'utilization_pct':float(values[0]),'vram_mib':float(values[1])}
 except Exception:return {'available':False}
def sample(n=3):
 values=[]
 for _ in range(n):values.append(gpu());time.sleep(.3)
 return values
trials=[]
for i in range(3):
 baseline=sample()
 r=requests.post(BASE+'/control/jobs',headers=HEADERS,json={'agent':'benson','prompt':'Cancellation measurement '+str(i)+': Print every integer from 1 through 10000 on separate lines. Do not summarize. Begin now.'},timeout=10)
 r.raise_for_status();job=r.json();deadline=time.monotonic()+20
 while get('jobs/'+job['id'])['status']=='queued' and time.monotonic()<deadline:time.sleep(.1)
 time.sleep(1)
 during=sample()
 before=get('jobs/'+job['id'])
 if before['status']!='running':
  trials.append({'trial':i+1,'valid':False,'reason':'Completed before cancellation','baseline':baseline,'during':during})
  continue
 started=time.monotonic()
 response=requests.post(BASE+'/control/jobs/'+job['id']+'/cancel',headers=HEADERS,timeout=10)
 response.raise_for_status()
 while time.monotonic()-started<15:
  current=get('jobs/'+job['id'])
  if current['status']=='cancelled':break
  time.sleep(.05)
 latency=round((time.monotonic()-started)*1000,1)
 time.sleep(2)
 after=sample()
 loaded=requests.get('http://127.0.0.1:11434/api/ps',timeout=5).json()
 trials.append({'trial':i+1,'valid':current['status']=='cancelled','cancel_ack_ms':latency,'request_stream_closed':bool(current['stream_closed']),'baseline':baseline,'during':during,'after':after,'loaded_models':[m['name'] for m in loaded.get('models',[])],'inference_stop':'unverified','model_unload_requested':False})
out=Path(__file__).resolve().parent.parent/'work'/'cancellation-measurements.json'
out.write_text(json.dumps(trials,indent=2),encoding='utf-8')
for trial in trials:print(json.dumps(trial))
if not all(t.get('valid') for t in trials):raise SystemExit(1)
