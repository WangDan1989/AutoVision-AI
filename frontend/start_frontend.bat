@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if not exist "node_modules" (
  echo node_modules 不存在，先执行 npm install
  exit /b 1
)

echo Starting frontend from %cd%
npm run dev

endlocal
