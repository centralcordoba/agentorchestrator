@echo off
REM Levanta la demo completa: PostgreSQL, backend y frontend, y siembra datos de ejemplo.
REM
REM   demo.bat            arranca todo (base en memoria si no hay Docker)
REM   demo.bat limpio     borra los datos anteriores antes de sembrar
REM
REM Deja dos ventanas abiertas (backend y frontend). Cerrarlas apaga la demo.
setlocal

set RAIZ=%~dp0
set BACKEND=%RAIZ%backend
set FRONTEND=%RAIZ%frontend
set PY=%BACKEND%\.venv\Scripts\python.exe
REM La clave de cifrado se guarda FUERA del repositorio y se reutiliza entre arranques: si
REM cambiara, lo guardado antes en PostgreSQL dejaria de poder descifrarse.
set CLAVE_DIR=%LOCALAPPDATA%\orq-demo
set CLAVE_ARCHIVO=%CLAVE_DIR%\clave.txt

if not exist "%PY%" (
  echo No existe %PY%
  echo Crea el entorno:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
  exit /b 1
)

REM ---- base de datos -----------------------------------------------------------
REM Sin Docker la demo funciona igual, pero los datos se pierden al reiniciar.
set DATABASE_URL=
docker ps >nul 2>&1
if not %errorlevel%==0 goto :sin_docker

docker start orq-postgres >nul 2>&1
if %errorlevel%==0 goto :hay_postgres
docker run -d --name orq-postgres -e POSTGRES_PASSWORD=orq -e POSTGRES_USER=orq -e POSTGRES_DB=orq -p 55432:5432 postgres:16-alpine >nul 2>&1
if not %errorlevel%==0 goto :sin_docker

:hay_postgres
set DATABASE_URL=postgresql://orq:orq@localhost:55432/orq
echo Base de datos: PostgreSQL en el 55432
goto :fin_docker

:sin_docker
echo Docker no responde: la demo usara memoria ^(los datos se pierden al reiniciar^)

:fin_docker

REM ---- clave de cifrado --------------------------------------------------------
REM Solo para la demo. En uso real viene de un gestor de secretos (ORQ-18).
REM Se genera solo la primera vez y se lee de disco: dentro de un for /f no caben comillas
REM anidadas.
if not defined DATABASE_URL goto :fin_clave
if defined DB_ENCRYPTION_KEY goto :fin_clave
if exist "%CLAVE_ARCHIVO%" goto :leer_clave
if not exist "%CLAVE_DIR%" mkdir "%CLAVE_DIR%" >nul 2>&1
pushd "%BACKEND%"
.venv\Scripts\python.exe scripts\new_key.py > "%CLAVE_ARCHIVO%" 2>nul
popd
echo Clave de cifrado nueva en %CLAVE_ARCHIVO%

:leer_clave
if exist "%CLAVE_ARCHIVO%" set /p DB_ENCRYPTION_KEY=<"%CLAVE_ARCHIVO%"

REM Sin clave no se arranca contra PostgreSQL: se sigue en memoria y se avisa.
if defined DB_ENCRYPTION_KEY goto :fin_clave
echo No se pudo generar la clave de cifrado: la demo usara memoria.
set DATABASE_URL=

:fin_clave

if not defined DATABASE_URL goto :fin_migraciones
pushd "%BACKEND%"
.venv\Scripts\python.exe -m alembic upgrade head >nul 2>&1
popd
if /i not "%1"=="limpio" goto :fin_migraciones
docker exec orq-postgres psql -U orq -d orq -c "TRUNCATE requirements, audit_entries, id_counters CASCADE;" >nul 2>&1
echo Datos anteriores borrados

:fin_migraciones

REM ---- proveedor de IA ---------------------------------------------------------
REM mock: sin claves, sin coste y sin red. El retardo deja ver la traza en vivo.
if not defined AI_PROVIDER set AI_PROVIDER=mock
if not defined AI_MOCK_DELAY_MS set AI_MOCK_DELAY_MS=1500
REM Informes con contenido de ejemplo, para que la demo se entienda. La UI avisa de que
REM son simulados. Con AI_MOCK_RICH=0 los agentes devuelven informes vacios.
if not defined AI_MOCK_RICH set AI_MOCK_RICH=1

REM ---- cuenta inicial ------------------------------------------------------------
REM Desde ORQ-5 la aplicacion pide entrar. Esta cuenta se crea la primera vez que
REM arranca el servicio, solo si no hay ninguna. En uso real se crea a mano y se cambia
REM la contrasena al entrar.
if not defined ADMIN_EMAIL set ADMIN_EMAIL=demo@orquestador.local
if not defined ADMIN_PASSWORD set ADMIN_PASSWORD=demo-orquestador-2026
set CORS_ORIGINS=http://localhost:3000
set NEXT_PUBLIC_ORQ_API_URL=http://localhost:8001

echo.
echo Arrancando backend  (http://localhost:8001/docs)
REM Las ventanas nuevas heredan el entorno de esta, asi que no hay que repetir las variables.
start "orquestador - backend" cmd /k "cd /d %BACKEND% && .venv\Scripts\python.exe -m uvicorn orq.main:app --port 8001"

echo Arrancando frontend (http://localhost:3000)
start "orquestador - frontend" cmd /k "cd /d %FRONTEND% && npm run dev"

echo.
echo Esperando a que el backend responda...

pushd "%BACKEND%"
.venv\Scripts\python.exe scripts\seed_demo.py
popd

echo.
echo Demo lista:  http://localhost:3000
echo Entra con:   %ADMIN_EMAIL% / %ADMIN_PASSWORD%
echo Contrato:    http://localhost:8001/docs
endlocal
