@echo off
REM ============================================================================
REM  AUTOMATIZADOR DOWNLOAD DE DADOS - Atualizador
REM  Sempre busca a versao MAIS RECENTE do programa no GitHub e atualiza tudo.
REM  Basta dar duplo-clique neste arquivo.
REM ============================================================================
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === Buscando a versao mais recente no GitHub... ===
git pull origin main
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel atualizar pelo git.
    echo Verifique sua conexao e se o GitHub Desktop esta logado.
    pause
    exit /b 1
)

REM Cria o ambiente virtual na primeira vez, se nao existir.
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo === Criando ambiente virtual (primeira vez)... ===
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
)

echo.
echo === Instalando/atualizando dependencias... ===
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo === Garantindo o navegador (Chromium)... ===
".venv\Scripts\python.exe" -m playwright install chromium

echo.
echo === Pronto! Voce esta na versao mais recente. ===
echo Use o run.bat para abrir o programa.
pause
