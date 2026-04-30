@echo off
REM Lokal test: cift tikla veya cmd'den: run_gateway.cmd
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [hata] Once kurulum: powershell -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
  exit /b 1
)
set "PYTHONPATH=%~dp0src"
echo --- .env ozeti ---
".venv\Scripts\python.exe" "%~dp0scripts\show_env_summary.py"
echo ------------------
".venv\Scripts\python.exe" -m dnp3_gateway
exit /b %ERRORLEVEL%
