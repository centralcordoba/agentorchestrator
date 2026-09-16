"""Deja la aplicación con datos para enseñarla.

Crea tres requerimientos en estados distintos llamando a la **API real**, no escribiendo en la
base: lo que se ve en la demo es exactamente lo que haría un usuario.

    cd backend
    .venv\\Scripts\\python.exe scripts/seed_demo.py

Con el proveedor `mock` los informes salen vacíos y marcados como simulados: el flujo es real,
el análisis todavía no. Eso es justo lo que hay que contar en la demo.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

BASE = "http://127.0.0.1:8001/api"

REQUIREMENTS = [
    {
        "title": "Conciliación de pagos del portal de pacientes",
        "description": (
            "La pantalla de pagos del portal no cuadra con la tabla de conciliación cuando el "
            "pago llega fuera de horario. Hay que corregir la consulta y la vista."
        ),
        "phi": "si",
        "acceptanceCriteria": [
            "El pago se concilia el mismo día aunque llegue fuera de horario",
            "El portal muestra el estado real de la conciliación",
        ],
        "attachments": [
            {"kind": "repo", "name": "acme/portal-pacientes", "detail": "rama feature/conciliacion"},
            {"kind": "vtr_template", "name": "VTR-modelo-v3.docx"},
            {"kind": "kiuwan_csv", "name": "kiuwan-portal-2026-09.csv", "detail": "1.240 filas"},
        ],
        "run": True,
    },
    {
        "title": "Exportar movimientos a CSV desde el back office",
        "description": (
            "Los administrativos piden poder exportar el listado de movimientos que ya ven en "
            "pantalla, con los mismos filtros."
        ),
        "phi": "no",
        "acceptanceCriteria": ["La exportación respeta los filtros aplicados"],
        "attachments": [
            {"kind": "repo", "name": "acme/backoffice", "detail": "rama feature/export-csv"},
            {"kind": "vtr_template", "name": "VTR-modelo-v3.docx"},
        ],
        "run": True,
    },
    {
        "title": "Nuevo endpoint de historia clínica resumida",
        "description": (
            "Servicio que devuelve el resumen de la historia clínica para la app móvil. Toca "
            "datos de paciente, así que el agente de Privacidad es obligatorio."
        ),
        "phi": "desconocido",
        "acceptanceCriteria": ["Devuelve el resumen en menos de 2 s"],
        # Sin plantilla VTR a propósito: en la demo se ve el bloqueo del plan.
        "attachments": [{"kind": "repo", "name": "acme/api-clinica", "detail": "rama feature/resumen"}],
        "run": False,
    },
]


def wait_for_api(client: httpx.Client, timeout_s: float = 90) -> dict:
    """Espera a que el backend responda. Arrancar tarda unos segundos la primera vez."""
    limite = time.monotonic() + timeout_s
    ultimo: Exception | None = None
    while time.monotonic() < limite:
        try:
            respuesta = client.get("/health")
            respuesta.raise_for_status()
            return respuesta.json()
        except httpx.HTTPError as error:
            ultimo = error
            time.sleep(1)
    raise SystemExit(
        f"El backend no respondió en {timeout_s:.0f} s ({ultimo}). "
        "Revisa su ventana: debería decir 'Uvicorn running on http://127.0.0.1:8001'."
    )


def seed(base: str, wait: bool, *, email: str, password: str) -> None:
    # Desde ORQ-5 la API exige sesión: se entra igual que lo haría una persona.
    with httpx.Client(base_url=base, timeout=30, follow_redirects=True) as client:
        config = wait_for_api(client)["config"]
        entrada = client.post("/auth/login", json={"email": email, "password": password})
        if entrada.status_code != 200:
            raise SystemExit(
                f"No se pudo entrar como {email}: {entrada.status_code}. "
                "Comprueba ADMIN_EMAIL y ADMIN_PASSWORD en el entorno del backend."
            )
        print(f"sesion iniciada como {entrada.json()['user']['email']}")
        modo = "con datos de ejemplo" if config.get("aiMockRich") else "sin datos de ejemplo"
        print(
            f"servicio ok · proveedor {config['aiProvider']} ({modo}) · base {config['database']}"
        )

        for spec in REQUIREMENTS:
            body = {k: v for k, v in spec.items() if k != "run"}
            requirement = client.post("/requirements", json=body).json()
            print(f"\n{requirement['id']} · {requirement['title']}")

            plan = client.post(f"/requirements/{requirement['id']}/plan").json()
            activos = plan["plan"]["enabledAgents"]
            print(f"  plan: {len(activos)} agente(s) · bloqueado: {plan['blocked']}")
            for warning in plan["warnings"]:
                marca = "BLOQUEO" if warning["blocks"] else "aviso"
                print(f"    [{marca}] {warning['text']}")

            if not spec["run"]:
                continue
            if plan["blocked"]:
                print("  no se lanza: el plan está bloqueado")
                continue

            run = client.post(
                f"/requirements/{requirement['id']}/runs", json={}
            ).json()
            print(f"  ejecución {run['id']} lanzada")
            if wait:
                estado = _wait(client, run["id"])
                print(f"  ejecución {run['id']}: {estado}")


def _wait(client: httpx.Client, run_id: str, timeout_s: float = 120) -> str:
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        estado = client.get(f"/runs/{run_id}").json()["run"]["status"]
        if estado != "en_curso":
            return estado
        time.sleep(0.5)
    return "sigue en curso"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE, help="URL de la API")
    parser.add_argument(
        "--no-wait", action="store_true", help="No esperar a que terminen las ejecuciones"
    )
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", ""), help="Cuenta con la que sembrar")
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", ""), help="Su contrasena")
    args = parser.parse_args()
    try:
        seed(args.base, wait=not args.no_wait, email=args.email, password=args.password)
    except httpx.HTTPError as error:
        print(f"\nNo se pudo hablar con la API en {args.base}: {error}", file=sys.stderr)
        print("¿Está levantado el backend? uvicorn orq.main:app --port 8001", file=sys.stderr)
        raise SystemExit(1)
    print("\nDatos de demo listos. Abre http://localhost:3000")
