@echo off
setlocal

echo ============================================================
echo  FARMA ANALYTICS - Cerrar agente local
echo ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$port = [int]($env:LOCAL_SYNC_AGENT_PORT -as [int]);" ^
  "if (-not $port) { $port = 8765 }" ^
  "$pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "if (-not $pids) { Write-Host 'No hay agente escuchando en el puerto' $port; exit 0 }" ^
  "foreach ($processId in $pids) { Write-Host 'Cerrando proceso' $processId 'en puerto' $port; Stop-Process -Id $processId -Force }"

echo.
echo Listo.
pause
endlocal
