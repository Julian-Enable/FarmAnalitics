@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo       Cerrando FarmaAnalytics Local
echo ==============================================
echo.

call "%~dp0cerrar_frontend.bat"
call "%~dp0cerrar_backend.bat"

echo.
echo Servicios cerrados.
endlocal
