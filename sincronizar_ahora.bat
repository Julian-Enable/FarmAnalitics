@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
".venv\Scripts\python.exe" sincronizar_smartpos_railway.py --recent-days 35 >> logs\sync_smartpos_railway_last_run.log 2>&1
if errorlevel 1 (
  echo Error sincronizando SmartPOS. Revisa logs\sync_smartpos_railway_last_run.log
  exit /b 1
)
echo Sincronizacion completa.
endlocal
