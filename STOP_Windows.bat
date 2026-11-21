@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto venv
python launcher.py --stop 2> nul || py -3 launcher.py --stop
goto end
:venv
.venv\Scripts\python.exe launcher.py --stop
:end
timeout /t 3 > nul
