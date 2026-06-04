@echo off
setlocal
cd /d "%~dp0"

echo [Backend] Cerrando instancia anterior en puerto 8002...
call "%~dp0cerrar_backend.bat"

if not exist ".venv\Scripts\python.exe" (
    echo [Backend] No existe .venv\Scripts\python.exe
    exit /b 1
)

echo [Backend] Iniciando FastAPI/Uvicorn en http://localhost:8002
start "Backend - FarmaAnalytics" /D "%~dp0" cmd.exe /k ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --reload"
endlocal
