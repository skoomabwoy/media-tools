@echo off
REM Launch Media Tools using the project's own virtualenv (Windows).
setlocal
set "HERE=%~dp0"
set "PYW=%HERE%.venv\Scripts\pythonw.exe"
if not exist "%PYW%" (
    echo Virtualenv not found. Set it up first by running:  uv sync
    echo (in this folder: %HERE%^)
    pause
    exit /b 1
)
start "Media Tools" "%PYW%" "%HERE%main.py" %*
