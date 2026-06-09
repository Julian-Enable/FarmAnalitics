@echo off
setlocal
set "ROOT_DIR=%~dp0..\.."
cd /d "%ROOT_DIR%"
".venv\Scripts\python.exe" descargar_historico.py --recent-days 35 --merge --dataset all
endlocal
