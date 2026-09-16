"""Genera una clave de cifrado para la base de datos.

    cd backend
    .venv\\Scripts\\python.exe scripts/new_key.py

La clave protege el contenido del cliente guardado en PostgreSQL. Guárdala fuera del repositorio
y fuera de la base; si se pierde, lo guardado con ella no se puede recuperar. En producción viene
de un gestor de secretos (ORQ-18), no de aquí.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from orq.infrastructure.db import Cipher  # noqa: E402

if __name__ == "__main__":
    print(Cipher.generate_key())
