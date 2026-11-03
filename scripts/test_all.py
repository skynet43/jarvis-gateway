"""Run the original regression suite and hardening tests without touching live data."""
import os,sys,tempfile,unittest
from pathlib import Path
root=Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path[:0]=[str(root),str(root/'src')]
os.environ['JARVIS_ADMIN_TOKEN']='test-only-token'
os.environ['JARVIS_TEST_TEMPLATES']='1'
import control
with tempfile.TemporaryDirectory() as directory:
 control.DB=Path(directory)/'regression.db'
 suite=unittest.defaultTestLoader.discover(str(root),pattern='tests_*.py')
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 sys.exit(not result.wasSuccessful())
