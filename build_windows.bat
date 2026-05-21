@echo off
setlocal
cd /d "%~dp0"

set PYTHON_BIN=%PYTHON_BIN%
if "%PYTHON_BIN%"=="" set PYTHON_BIN=.\.venv\Scripts\python.exe

if not exist "%PYTHON_BIN%" (
  echo Expected Python interpreter at %PYTHON_BIN%
  exit /b 1
)

"%PYTHON_BIN%" -m pip install -r requirements.txt || exit /b 1
"%PYTHON_BIN%" -m PyInstaller --noconfirm --windowed --name HireFlow --add-data "templates;templates" --add-data "assets;assets" --add-data "samples;samples" --collect-data certifi --collect-submodules keyring main.py
