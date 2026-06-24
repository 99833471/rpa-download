@echo off
REM Atalho para rodar o app usando o ambiente virtual local.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Crie com:
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
