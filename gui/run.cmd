@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  echo Run create_env.cmd first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m gui
if errorlevel 1 pause
