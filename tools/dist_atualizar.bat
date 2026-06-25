@echo off
REM Atualiza esta copia do AUTOMATIZADOR para a versao mais recente do GitHub.
REM Feche o programa antes de rodar. Duplo-clique para usar.
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_update.ps1"
echo.
pause
