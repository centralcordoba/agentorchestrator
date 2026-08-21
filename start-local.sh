#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Arranque "un solo proceso" (sin Docker ni Node): FastAPI sirve la API y el
# frontend estático (frontend/out, generado con `npm run build:static`).
#
# Requisitos en esta máquina: Python 3.10+ (instalación de usuario basta).
# Sin internet: copia antes una carpeta backend/wheels con las dependencias
# (ver README, "Modo un solo proceso").
# ------------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/backend"

PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python

if [ ! -x ".venv/bin/python" ] && [ ! -x ".venv/Scripts/python.exe" ]; then
  echo "[1/3] Creando entorno virtual..."
  "$PY" -m venv .venv
fi
VENV_PY=".venv/bin/python"; [ -x "$VENV_PY" ] || VENV_PY=".venv/Scripts/python.exe"

echo "[2/3] Instalando dependencias..."
if [ -d wheels ]; then
  "$VENV_PY" -m pip install --no-index --find-links wheels -r requirements.txt -q
else
  "$VENV_PY" -m pip install -r requirements.txt -q
fi

if [ ! -f "../frontend/out/index.html" ]; then
  echo
  echo "AVISO: no existe frontend/out/index.html. Solo se servirá la API."
  echo "       Genera el frontend estático en una máquina con Node: cd frontend && npm run build:static"
  echo
fi

export LLM_PROVIDER=${LLM_PROVIDER:-mock}
export MARKET_DATA_PROVIDER=${MARKET_DATA_PROVIDER:-mock}
echo "[3/3] Arrancando en http://localhost:8000  (Ctrl+C para parar)"
exec "$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
