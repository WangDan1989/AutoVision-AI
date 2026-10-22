@echo off
chcp 65001 >nul
setlocal

set "BD=%~dp0"
cd /d "%BD%"

if not exist "storage" mkdir "storage"
if not exist "storage\images" mkdir "storage\images"
if not exist "storage\videos" mkdir "storage\videos"
if not exist "storage\audio" mkdir "storage\audio"
if not exist "storage\exports" mkdir "storage\exports"
if not exist "storage\loras" mkdir "storage\loras"
if not exist "storage\temp" mkdir "storage\temp"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=py"
)

echo Starting backend from %BD%
echo Using interpreter: %PYTHON_EXE%

if "%PYTHON_EXE%"=="py" (
  py -3.12 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) else (
  "%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
)

endlocal
