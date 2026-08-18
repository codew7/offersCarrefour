@echo off
chcp 65001 >nul
title Verificador de precios Carrefour
cd /d "%~dp0"

rem ------------------------------------------------------------------
rem  Busca un Python que REALMENTE funcione.
rem  No alcanza con "where py": Windows 10/11 trae un acceso directo
rem  vacio a la Microsoft Store llamado py.exe / python.exe que existe,
rem  no ejecuta nada y devuelve error. Por eso probamos cada uno.
rem ------------------------------------------------------------------
set "PY="
py -3 -c "pass" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "pass" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "pass" >nul 2>&1 && set "PY=python3"

if not defined PY (
    echo.
    echo ============================================================
    echo  No encontre Python funcionando en esta computadora.
    echo ============================================================
    echo.
    echo  Instalalo una sola vez desde:
    echo      https://www.python.org/downloads/
    echo.
    echo  IMPORTANTE: en la primera pantalla del instalador tilda
    echo  la casilla "Add python.exe to PATH" antes de continuar.
    echo.
    echo  Despues volve a hacer doble clic en este archivo.
    echo.
    pause
    exit /b 1
)

echo Iniciando con: %PY%
echo.
%PY% verificador.py
set "CODIGO=%errorlevel%"

rem Si Python murio con error, la ventana se queda abierta para poder leerlo.
if not "%CODIGO%"=="0" (
    echo.
    echo ============================================================
    echo  El programa se cerro con un error ^(codigo %CODIGO%^).
    echo  Copia el texto de arriba: ahi dice que paso.
    echo ============================================================
    pause
)
exit /b %CODIGO%
