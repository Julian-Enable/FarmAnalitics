@echo off
setlocal
set "ROOT_DIR=%~dp0..\.."
cd /d "%ROOT_DIR%"

echo ==============================================
echo       Cerrando FarmaAnalytics Local
echo ==============================================
echo.

call "%~dp0cerrar_frontend.bat"
call "%~dp0cerrar_backend.bat"

echo.
echo Servicios cerrados.
endlocal
