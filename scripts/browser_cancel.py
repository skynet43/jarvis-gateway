"""Compatibility entry point for browser cancellation acceptance."""
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
raise SystemExit(subprocess.run(['cmd.exe','/d','/c','npm test -- --grep "queued and running"'],cwd=root/'frontend').returncode)
