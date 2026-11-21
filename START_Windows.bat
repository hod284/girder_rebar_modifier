@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Girder Rebar Modifier
set "DIR=%CD%"
set "VPY=%DIR%\.venv\Scripts\python.exe"
set "CHK_VER=import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)"
set "CHK_DEP=import ifcopenshell, plotly, pandas, matplotlib, numpy, streamlit as s, sys; sys.exit(0 if tuple(int(x) for x in s.__version__.split('.')[:2])>=(1,50) else 1)"
echo ==================================================
echo   Girder Rebar Modifier - start / restart
echo   1. Installed Python + libraries found : run directly, no install
echo   2. Only Python found                 : install libraries into this folder
echo   3. No Python                         : install private Python into this folder
echo ==================================================

rem ---- 0) this folder's .venv already ready
if not exist "%VPY%" goto findpy
"%VPY%" -c "%CHK_DEP%" > nul 2>&1
if errorlevel 1 goto findpy
set RUNCMD="%VPY%"
goto run

rem ---- 1) installed Python
:findpy
set "BASE="
python -c "%CHK_VER%" > nul 2>&1
if errorlevel 1 goto trypy
python -c "%CHK_DEP%" > nul 2>&1
if errorlevel 1 goto basepython
echo [OK] Using installed Python and libraries. No install needed.
set RUNCMD=python
goto run
:basepython
set "BASE=python"
:trypy
py -3 -c "%CHK_VER%" > nul 2>&1
if errorlevel 1 goto decide
py -3 -c "%CHK_DEP%" > nul 2>&1
if errorlevel 1 goto basepy
echo [OK] Using installed Python and libraries. No install needed.
set RUNCMD=py -3
goto run
:basepy
if not defined BASE set "BASE=py -3"
:decide
if defined BASE goto venvbase
goto uvsetup

rem ---- 2) Python only: install libraries into .venv
:venvbase
echo.
echo [SETUP] Using installed Python. Installing libraries into this folder only. 1-3 min, first run only
if exist "%DIR%\.venv" rmdir /s /q "%DIR%\.venv"
%BASE% -m venv "%DIR%\.venv"
if errorlevel 1 goto failpy
"%VPY%" -m pip install -q --upgrade pip
"%VPY%" -m pip install -r "%DIR%\requirements.txt"
if errorlevel 1 goto faillib
echo [SETUP] Done
set RUNCMD="%VPY%"
goto run

rem ---- 3) No Python: private Python via uv
:uvsetup
echo.
echo [SETUP] No Python found. Installing private Python + libraries into this folder. 2-5 min, first run only
set "UV_INSTALL_DIR=%DIR%\.uv"
set "UV_NO_MODIFY_PATH=1"
set "INSTALLER_NO_MODIFY_PATH=1"
set "UV_PYTHON_INSTALL_DIR=%DIR%\.uv\python"
set "UV_CACHE_DIR=%DIR%\.uv\cache"
set "UV="
if exist "%DIR%\.uv\uv.exe" set "UV=%DIR%\.uv\uv.exe"
if exist "%DIR%\.uv\bin\uv.exe" set "UV=%DIR%\.uv\bin\uv.exe"
if defined UV goto haveuv
echo [SETUP] 1/3 Downloading installer uv...
powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex" > "%DIR%\.uv_install.log" 2>&1
if exist "%DIR%\.uv\uv.exe" set "UV=%DIR%\.uv\uv.exe"
if exist "%DIR%\.uv\bin\uv.exe" set "UV=%DIR%\.uv\bin\uv.exe"
if not defined UV goto failuv
:haveuv
echo [SETUP] 2/3 Installing private Python 3.12...
if exist "%DIR%\.venv" rmdir /s /q "%DIR%\.venv"
"%UV%" venv "%DIR%\.venv" --python 3.12 --managed-python --seed -q
if errorlevel 1 goto failpy
echo [SETUP] 3/3 Installing libraries... takes the longest
"%UV%" pip install --python "%VPY%" -r "%DIR%\requirements.txt"
if errorlevel 1 goto faillib
echo [SETUP] Done
set RUNCMD="%VPY%"

:run
%RUNCMD% launcher.py
if errorlevel 1 goto failrun
echo.
echo The program is open in your web browser. You can close this window.
timeout /t 5 > nul
exit /b 0

:failuv
echo [ERROR] Could not download installer uv. Check internet and run again.
pause
exit /b 1
:failpy
echo [ERROR] Python setup failed. Check internet and run again.
pause
exit /b 1
:faillib
if exist "%DIR%\.venv" rmdir /s /q "%DIR%\.venv"
echo [ERROR] Library install failed. Check internet and run again.
pause
exit /b 1
:failrun
echo [ERROR] Failed to start. See app.log in this folder.
pause
exit /b 1
