from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BACKEND_DIR / "storage"
LOG_OUT = STORAGE_DIR / "uvicorn_server.log"
LOG_ERR = STORAGE_DIR / "uvicorn_crash.log"


def resolve_python() -> str:
    venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    launcher = shutil.which("py")
    if launcher:
        return launcher
    return sys.executable


def build_command(python_exe: str) -> list[str]:
    if Path(python_exe).name.lower() == "py.exe" or Path(python_exe).name.lower() == "py":
        return [python_exe, "-3.12", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    return [python_exe, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


def main() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    pythonpath = str(BACKEND_DIR)
    env["PYTHONPATH"] = pythonpath + (os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else pythonpath

    python_exe = resolve_python()
    command = build_command(python_exe)

    with LOG_OUT.open("a", encoding="utf-8") as stdout_file, LOG_ERR.open("a", encoding="utf-8") as stderr_file:
        marker = f"\n===== SPAWN START {datetime.now().isoformat()} =====\n"
        stdout_file.write(marker)
        stderr_file.write(marker)
        process = subprocess.Popen(
            command,
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x00000008),
            close_fds=True,
        )
    print(f"BACKEND_PID={process.pid}", flush=True)
    print(f"PYTHON={python_exe}", flush=True)


if __name__ == "__main__":
    main()
