@echo off
REM ------------------------------------------------------------------------------
REM Arranque "un solo proceso" (sin Docker ni Node): FastAPI sirve la API y el
REM frontend estatico (frontend\out, generado con `npm run build:static`).
REM
REM Requisitos en esta maquina: Python 3.10+ (instalacion de usuario basta).
REM Sin internet: copia antes una carpeta backend\wheels con las dependencias
REM (ver README, "Modo un solo proceso").
REM ------------------------------------------------------------------------------
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual...
    python -m venv .venv || goto :fail
)

echo [2/3] Instalando dependencias...
if exist "wheels" (
    .venv\Scripts\python -m pip install --no-index --find-links wheels -r requirements.txt -q || goto :fail
) else (
    .venv\Scripts\python -m pip install -r requirements.txt -q || goto :fail
)

if not exist "..\frontend\out\index.html" (
    echo.
    echo AVISO: no existe frontend\out\index.html. Solo se servira la API.
    echo        Genera el frontend estatico en una maquina con Node: cd frontend ^&^& npm run build:static
    echo.
)

echo [3/3] Arrancando en http://localhost:8000  (Ctrl+C para parar)
if "%LLM_PROVIDER%"=="" set LLM_PROVIDER=mock
if "%MARKET_DATA_PROVIDER%"=="" set MARKET_DATA_PROVIDER=mock
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

:fail
echo.
echo ERROR: fallo la preparacion del entorno. Revisa que `python` este en el PATH.
pause
exit /b 1
