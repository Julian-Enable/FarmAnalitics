@echo off
setlocal
set "ROOT_DIR=%~dp0..\.."
cd /d "%ROOT_DIR%"

echo [Frontend] Cerrando instancia anterior en puerto 5173...
call "%~dp0cerrar_frontend.bat"

if not exist "frontend\package.json" (
    echo [Frontend] No existe frontend\package.json
    exit /b 1
)

echo [Frontend] Iniciando Vite en http://localhost:5173
start "Frontend - FarmaAnalytics" /D "%ROOT_DIR%\frontend" cmd.exe /k "npm run dev -- --host 127.0.0.1"
endlocal
