"""Compatibility entry point for the current isolated Chromium acceptance suite."""
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent
raise SystemExit(subprocess.run(['cmd.exe','/d','/c','npm test'],cwd=root/'frontend').returncode)
