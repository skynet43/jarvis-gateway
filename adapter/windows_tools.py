"""Strict read-only filesystem and owned-process automation for Windows."""
import csv
import os
import subprocess
from pathlib import Path

TEXT_EXTENSIONS = {".md", ".py", ".ts", ".tsx", ".css", ".html", ".json", ".txt", ".ps1", ".sh"}
SENSITIVE = ("secret", "token", "credential", "password", ".env")
REPARSE_POINT = 0x400


class WindowsTools:
    def __init__(self, roots, executables):
        self.roots = tuple(Path(root).resolve(strict=True) for root in roots)
        self.executables = {Path(item).resolve(strict=True) for item in executables}
        if not self.roots:
            raise ValueError("At least one automation root is required")
        self.owned = {}

    def _target(self, value, *, must_exist=True):
        raw = Path(value)
        try:
            target = raw.resolve(strict=must_exist)
        except OSError:
            raise ValueError("Path does not exist") from None
        if not any(target == root or target.is_relative_to(root) for root in self.roots):
            raise ValueError("Path is outside configured roots")
        for part in (target, *target.parents):
            if part in self.roots:
                break
            try:
                if part.stat().st_file_attributes & REPARSE_POINT:
                    raise ValueError("Reparse points are not allowed")
            except AttributeError:
                pass
        if any(term in part.lower() for part in target.parts for term in SENSITIVE):
            raise ValueError("Sensitive path is not allowed")
        return target

    def list_files(self, path):
        target = self._target(path)
        if not target.is_dir():
            raise ValueError("Directory required")
        names = []
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            try:
                self._target(child)
                names.append(child.name + ("/" if child.is_dir() else ""))
            except (OSError, ValueError):
                continue
        return names[:200]

    def file_metadata(self, path):
        target = self._target(path)
        stat = target.stat()
        return {
            "name": target.name, "is_directory": target.is_dir(),
            "size": stat.st_size, "modified": stat.st_mtime,
        }

    def read_text(self, path):
        target = self._target(path)
        if not target.is_file() or target.suffix.lower() not in TEXT_EXTENSIONS:
            raise ValueError("Approved text file required")
        if target.stat().st_size > 262144:
            raise ValueError("File exceeds 256 KiB")
        return {"name": target.name, "content": target.read_text("utf-8", errors="replace")[:12000]}

    def list_processes(self, limit=100):
        limit = max(1, min(int(limit), 200))
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
            timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError("Process listing failed")
        rows = []
        for row in csv.reader(result.stdout.splitlines()):
            if len(row) >= 2 and row[1].replace(",", "").isdigit():
                rows.append({"name": row[0][:200], "pid": int(row[1].replace(",", ""))})
        return rows[:limit]

    def start_process(self, executable, arguments):
        try:
            path = Path(executable).resolve(strict=True)
        except OSError:
            raise ValueError("Executable does not exist") from None
        if path not in self.executables:
            raise ValueError("Executable is not allowlisted")
        if not isinstance(arguments, list) or len(arguments) > 32:
            raise ValueError("Arguments must be an array of at most 32 strings")
        clean = []
        for argument in arguments:
            if (not isinstance(argument, str) or len(argument) > 1024
                    or any(c in argument for c in "\x00\r\n&|;<>") ):
                raise ValueError("Invalid process argument")
            clean.append(argument)
        process = subprocess.Popen(
            [str(path), *clean], shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.owned[process.pid] = process
        return {"pid": process.pid, "status": "running"}

    def stop_process(self, pid):
        process = self.owned.pop(int(pid), None)
        if process is None:
            raise ValueError("Process is not owned by this adapter session")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return {"pid": process.pid, "status": "stopped"}

    def close(self):
        for pid in list(self.owned):
            try:
                self.stop_process(pid)
            except (OSError, ValueError):
                pass
