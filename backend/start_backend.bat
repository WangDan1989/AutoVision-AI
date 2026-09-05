@echo off
chcp 65001 >nul
setlocal
set "BD=c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend"
set "PY=D:\ComfyUI_windows_portable\python_embeded\python.exe"
set "LOG=%BD%\storage\uvicorn_server.log"
set "ERR=%BD%\storage\uvicorn_crash.log"
if not exist "%BD%\storage" mkdir "%BD%\storage"
echo ===== RESTART %date% %time% ===== >> "%LOG%"
echo ===== RESTART %date% %time% ===== >> "%ERR%"
set PYTHONPATH=%BD%;%BD%\libs
cd /d "%BD%"
start "AutoVision-Backend" /min "%PY%" -u "%BD%\__run_server.py" >>"%LOG%" 2>>"%ERR%"
endlocal
