@echo off
chcp 65001 >nul
title Servidor Limpeza — Minde

echo.
echo  Verificar Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Python nao encontrado.
    echo  Instale em https://www.python.org/downloads/
    echo  Certifique-se de marcar "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo  Verificar Flask...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo  Flask nao instalado. A instalar agora...
    pip install flask
    if errorlevel 1 (
        echo  ERRO ao instalar Flask. Verifique a sua ligacao a internet.
        pause
        exit /b 1
    )
)

echo.
echo  A iniciar servidor...
echo  Nao feche esta janela enquanto o site estiver a ser utilizado.
echo.
python server.py
pause
