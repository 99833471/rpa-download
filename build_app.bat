@echo off
REM Gera o aplicativo standalone (.exe em pasta + .zip) na pasta dist\.
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Rode antes:  atualizar.bat
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller --quiet
".venv\Scripts\python.exe" tools\build_app.py
pause
