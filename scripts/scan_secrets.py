"""Targeted credential scan. Reports locations only, never matched values."""
import json,os,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
token=os.environ.get('JARVIS_ADMIN_TOKEN','').encode()
patterns=[re.compile(rb'AKIA[0-9A-Z]{16}'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'sk-[A-Za-z0-9_-]{32,}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
def contains(data):
 return bool((token and len(token)>8 and token in data) or any(p.search(data) for p in patterns))
findings=[]
paths=git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
for name in filter(None,paths):
 path=root/name
 if path.is_file() and contains(path.read_bytes()):findings.append({'scope':'working_tree','path':name})
objects={}
for line in git('rev-list','--objects','--all').decode().splitlines():
 oid,_,name=line.partition(' ')
 objects[oid]=name
payload=''.join(oid+'\n' for oid in objects).encode()
proc=subprocess.run(['git','cat-file','--batch'],cwd=root,input=payload,capture_output=True,check=True)
data=proc.stdout;position=0;blobs=0
while position<len(data):
 end=data.index(b'\n',position)
 oid,kind,size=data[position:end].decode().split()
 position=end+1;size=int(size);body=data[position:position+size];position+=size+1
 if kind=='blob':
  blobs+=1
  if contains(body):findings.append({'scope':'git_history','object':oid,'path':objects[oid]})
result={'working_files':len([p for p in paths if p]),'history_blobs':blobs,'patterns':'current configured token, AWS access-key IDs, GitHub tokens, sk-prefixed keys, private-key headers','findings':findings,'limitation':'Targeted patterns cannot prove absence of every possible secret.'}
(root/'work').mkdir(exist_ok=True)
(root/'work'/'secret-scan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
raise SystemExit(bool(findings))
