@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

echo ============================================================
echo  FARMA ANALYTICS - Sincronizacion SmartPOS hacia Railway
echo ============================================================
echo.
echo Inicio: %date% %time%
echo.
echo Esta ventana mostrara el avance en vivo.
echo Tambien se guardara copia en:
echo   logs\sync_smartpos_railway_last_run.log
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$env:PYTHONUNBUFFERED='1';" ^
  "$log='logs\sync_smartpos_railway_last_run.log';" ^
  "'============================================================' | Tee-Object -FilePath $log;" ^
  "'Inicio: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Tee-Object -FilePath $log -Append;" ^
  "'.venv\Scripts\python.exe sincronizar_smartpos_railway.py --recent-days 35 --skip-validate' | Tee-Object -FilePath $log -Append;" ^
  "& '.venv\Scripts\python.exe' 'sincronizar_smartpos_railway.py' --recent-days 35 --skip-validate 2>&1 | Tee-Object -FilePath $log -Append;" ^
  "exit $LASTEXITCODE"

if errorlevel 1 (
  echo.
  echo ERROR: La sincronizacion fallo.
  echo Revisa el detalle en logs\sync_smartpos_railway_last_run.log
  pause
  exit /b 1
)

echo.
echo Sincronizacion completa: %date% %time%
echo Ya puedes actualizar la pagina de Farma Analytics.
pause
endlocal
