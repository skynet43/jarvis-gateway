"""Isolated acceptance server; never uses the user's database or admin token."""
import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
if not os.environ.get('JARVIS_ACCEPTANCE_TOKEN'):
 raise SystemExit('Acceptance token must be supplied by the test runner')
os.environ['JARVIS_ADMIN_TOKEN']=os.environ['JARVIS_ACCEPTANCE_TOKEN']
os.environ['JARVIS_TEST_TEMPLATES']='1'
with tempfile.TemporaryDirectory(prefix='jarvis-browser-') as directory:
 os.environ['JARVIS_DB']=str(Path(directory)/'test.db')
 import uvicorn
 uvicorn.run('gateway:app',host='127.0.0.1',port=8766,log_level='warning')
