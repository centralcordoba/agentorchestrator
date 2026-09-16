"""El contrato publicado no se desfasa.

`backend/openapi.json` está versionado y de él se generan los tipos del frontend. Si alguien
cambia una respuesta y no regenera el contrato, el frontend compilaría contra una API que ya no
existe. Esta prueba lo impide desde el lado del backend; `npm run api:check` lo impide desde el
del frontend.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from orq.config import Settings
from orq.main import create_app

from .conftest import logged_client
from scripts.export_openapi import DESTINATION


@pytest.fixture(scope="module")
def schema() -> dict:
    app = create_app(Settings(database_url="", cors_origins=()))
    return app.openapi()


def test_committed_contract_is_up_to_date(schema: dict) -> None:
    assert DESTINATION.exists(), "Falta backend/openapi.json: expórtalo con scripts/export_openapi.py"
    committed = json.loads(DESTINATION.read_text(encoding="utf-8"))
    assert committed == schema, (
        "El contrato versionado no coincide con la API. Ejecuta:\n"
        "  .venv\\Scripts\\python.exe scripts/export_openapi.py\n"
        "y regenera los tipos del frontend con: npm run api:types"
    )


def test_every_response_field_is_camel_case(schema: dict) -> None:
    """El contrato lo consume TypeScript: nada de snake_case en las respuestas."""
    offenders: list[str] = []
    for name, definition in schema["components"]["schemas"].items():
        for field in (definition.get("properties") or {}):
            # Las claves indexadas por agente (`code`, `tests`…) no llevan guion bajo tampoco.
            if "_" in field:
                offenders.append(f"{name}.{field}")
    assert not offenders, "Campos en snake_case: " + ", ".join(offenders)


def test_errors_are_part_of_the_contract(schema: dict) -> None:
    assert "ApiError" in schema["components"]["schemas"]
    responses = schema["paths"]["/api/requirements/{requirement_id}"]["get"]["responses"]
    assert "404" in responses
    error_ref = responses["404"]["content"]["application/json"]["schema"]["$ref"]
    assert error_ref.endswith("ApiError")


def test_error_body_matches_the_documented_shape(settings) -> None:
    """Lo documentado y lo que sale de verdad son lo mismo.

    También sin sesión: un 401 tiene la misma forma que cualquier otro error, para que el cliente
    lo trate igual (ORQ-5).
    """
    sin_sesion = TestClient(create_app(Settings(database_url="", cors_origins=())))
    respuesta = sin_sesion.get("/api/requirements/REQ-999")
    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert set(cuerpo) <= {"code", "message", "detail"}
    assert cuerpo["code"] == "NotAuthenticatedError"

    cliente, _ = logged_client(settings)
    cuerpo = cliente.get("/api/requirements/REQ-999").json()
    assert set(cuerpo) <= {"code", "message", "detail"}
    assert cuerpo["code"] == "NotFoundError"
    assert cuerpo["message"]


def test_paginated_lists_share_the_same_shape(schema: dict) -> None:
    for name in ("RequirementPage", "RunPage", "AuditPage"):
        page = schema["components"]["schemas"][name]
        assert set(page["properties"]) == {"items", "total", "limit", "offset"}, name
