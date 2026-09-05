import sys
import subprocess
import os

_BACKEND = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend"
_LIBS = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend\libs"
_PYTHON = r"D:\ComfyUI_windows_portable\python_embeded\python.exe"
_LOG_OUT = os.path.join(_BACKEND, "storage", "uvicorn_server.log")
_LOG_ERR = os.path.join(_BACKEND, "storage", "uvicorn_crash.log")

os.makedirs(os.path.dirname(_LOG_OUT), exist_ok=True)

_env = os.environ.copy()
_pp = _BACKEND + os.pathsep + _LIBS
_env["PYTHONPATH"] = _pp + (os.pathsep + _env["PYTHONPATH"]) if _env.get("PYTHONPATH") else _pp

with open(_LOG_OUT, "a", encoding="utf-8") as fo, open(_LOG_ERR, "a", encoding="utf-8") as fe:
    fo.write(f"\n===== SPAWN START {__import__('datetime').datetime.now()} =====\n")
    fe.write(f"\n===== SPAWN START {__import__('datetime').datetime.now()} =====\n")
    p = subprocess.Popen(
        [_PYTHON, "-u", os.path.join(_BACKEND, "__run_server.py")],
        cwd=_BACKEND,
        env=_env,
        stdout=fo,
        stderr=fe,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x00000008),
        close_fds=True,
    )
    print("BACKEND_PID=", p.pid, flush=True)
