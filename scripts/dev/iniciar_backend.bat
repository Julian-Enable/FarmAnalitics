@echo off
setlocal
set "ROOT_DIR=%~dp0..\.."
cd /d "%ROOT_DIR%"

echo [Backend] Cerrando instancia anterior en puerto 8002...
call "%~dp0cerrar_backend.bat"

if not exist ".venv\Scripts\python.exe" (
    echo [Backend] No existe .venv\Scripts\python.exe
    exit /b 1
)

echo [Backend] Iniciando FastAPI/Uvicorn en http://localhost:8002
start "Backend - FarmaAnalytics" /D "%ROOT_DIR%" cmd.exe /k ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --reload"
endlocal
