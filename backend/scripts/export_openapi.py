"""Exporta el contrato de la API a `backend/openapi.json`.

Ese archivo está versionado a propósito: de él se generan los tipos de TypeScript
(`cd frontend && npm run api:types`) y en él se ve en una revisión si un cambio del backend
altera el contrato. Si el archivo se queda atrás, `npm run api:check` falla.

    cd backend
    .venv\\Scripts\\python.exe scripts/export_openapi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from orq.config import Settings  # noqa: E402
from orq.main import create_app  # noqa: E402

DESTINATION = BACKEND_DIR / "openapi.json"


def export() -> Path:
    # Sin base de datos ni claves: el contrato no depende de la configuración del entorno.
    app = create_app(Settings(database_url="", cors_origins=()))
    schema = app.openapi()
    DESTINATION.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return DESTINATION


if __name__ == "__main__":
    path = export()
    print(f"contrato escrito en {path}")
