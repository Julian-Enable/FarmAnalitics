@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  FARMA ANALYTICS - Agente local para actualizar desde la web
echo ============================================================
echo.
echo Este agente permite que farm-analitics.vercel.app ejecute
echo la sincronizacion SmartPOS - Railway desde ESTE PC.
echo.
echo Deja esta ventana abierta mientras quieras usar el boton:
echo   Actualizar desde este PC
echo.
echo Para cerrar el agente presiona Ctrl+C o ejecuta cerrar_agente_sync.bat
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" agente_sync_local.py
) else (
  python agente_sync_local.py
)

echo.
echo El agente se cerro.
pause
endlocal
