@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" descargar_historico.py --recent-days 35 --merge --dataset all
endlocal
