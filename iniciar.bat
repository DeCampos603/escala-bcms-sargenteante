@echo off
chcp 65001 > nul
title EscalaPro BCMS - Servidor Local (UASG 160329)

cd /d "%~dp0"

echo ======================================================================
echo    ESCALAPRO BCMS - PREVISAO E CONTROLE DE ESCALAS DE SERVICO
echo    Batalhao Central de Manutencao e Suprimento / Ba Ap Log Ex
echo ======================================================================
echo.

:: Verifica se a porta 8770 ja esta ativa
netstat -ano | findstr :8770 > nul
if %errorlevel% equ 0 (
    echo O servidor EscalaPro BCMS ja esta ativo em segundo plano!
    echo Abrindo o painel de controle no navegador...
    start "" "http://127.0.0.1:8770"
    timeout /t 3 > nul
    exit
)

echo Iniciando servidor local na porta 8770...
echo Acesse no navegador: http://127.0.0.1:8770
echo.

start "" "http://127.0.0.1:8770"
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8770 --reload
pause
