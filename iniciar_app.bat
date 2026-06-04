@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo       Iniciando FarmaAnalytics Local
echo ==============================================
echo.

call "%~dp0iniciar_backend.bat"
call "%~dp0iniciar_frontend.bat"

echo.
echo ==============================================
echo Servicios iniciados.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8002/docs
echo ==============================================
echo.
endlocal
