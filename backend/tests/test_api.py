"""API HTTP: el mismo flujo, esta vez por la red."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from orq.api.container import Container
from orq.main import create_app

from .conftest import make_user


@pytest.fixture
def client(container: Container, settings):
    """Cliente con sesión abierta y el ciclo de vida de la app activo.

    Se usa como contexto a propósito: así se ejecuta el `lifespan` (que reanuda ejecuciones
    interrumpidas) y las ejecuciones en segundo plano sobreviven entre peticiones.

    Desde ORQ-5 entra por `/api/auth/login` como lo haría una persona: ninguna ruta de datos
    responde sin sesión.
    """
    make_user(container)
    with TestClient(create_app(settings, container=container)) as client:
        respuesta = client.post(
            "/api/auth/login",
            json={"email": "ana@acme.test", "password": "contrasena-de-prueba-larga"},
        )
        assert respuesta.status_code == 200, respuesta.text
        yield client


def wait_for_run(client: TestClient, run_id: str, *, timeout: float = 10.0) -> dict:
    """La ejecución va en segundo plano: se consulta hasta que termina."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["run"]["status"] != "en_curso":
            return body
        time.sleep(0.05)
    raise AssertionError(f"La ejecución {run_id} no terminó en {timeout}s")


def test_health_reports_status_without_leaking_credentials(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["config"]["aiProvider"] == "mock"
    # Solo se dice si hay clave configurada, nunca su valor.
    config = body["config"]
    assert isinstance(config["anthropicKeyConfigured"], bool)
    assert isinstance(config["openrouterKeyConfigured"], bool)
    # Ninguna clave viaja: solo se dice si está configurada.
    assert not [k for k in config if k.endswith("ApiKey") or k.endswith("Key")]
    assert not [v for v in config.values() if isinstance(v, str) and v.startswith("sk-")]


def test_agent_catalog_is_exposed_as_read_only(client: TestClient) -> None:
    body = client.get("/api/catalog/agents").json()
    assert body["order"][0] == "orchestrator"
    assert "chat" in body["all"] and "chat" not in body["order"]
    code = body["agents"]["code"]
    assert code["tools"] and code["outputSchema"]["type"] == "object"
    assert code["requiresAttachment"] == "repo"


def test_model_catalog_shows_the_baa_flag(client: TestClient) -> None:
    providers = client.get("/api/catalog/models").json()["providers"]
    assert providers["anthropic"]["baa"] is True
    assert providers["openrouter"]["baa"] is False
    assert providers["mock"]["baa"] is None


def _create_requirement(client: TestClient) -> str:
    response = client.post(
        "/api/requirements",
        json={
            "title": "Conciliación de pagos del portal",
            "description": "Ajustar la pantalla de pagos y la consulta de la tabla.",
            "acceptanceCriteria": ["El pago se concilia el mismo día"],
            "phi": "desconocido",
            "attachments": [
                {"kind": "repo", "name": "org/repo"},
                {"kind": "vtr_template", "name": "plantilla.docx"},
                {"kind": "kiuwan_csv", "name": "kiuwan.csv"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["handlesPhi"] is True
    assert body["acceptanceCriteria"] == ["El pago se concilia el mismo día"]
    return body["id"]


def test_full_flow_over_http(client: TestClient) -> None:
    requirement_id = _create_requirement(client)

    plan = client.post(f"/api/requirements/{requirement_id}/plan").json()
    assert plan["blocked"] is False
    assert {item["agentId"] for item in plan["plan"]["items"] if item["enabled"]}

    run = client.post(
        f"/api/requirements/{requirement_id}/runs", json={}
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]
    # Responde de inmediato: la revisión sigue en segundo plano.
    assert run.json()["status"] == "en_curso"
    assert wait_for_run(client, run_id)["run"]["status"] == "completada"

    detail = client.get(f"/api/runs/{run_id}", params={"events": True}).json()
    assert detail["run"]["profiles"]["code"]["provider"] == "mock"
    # Cada agente publica el registro de sus llamadas: metadatos, nunca contenido.
    call = detail["run"]["executions"]["code"]["calls"][0]
    assert call["provider"] == "mock" and call["promptVersion"] == 1
    assert not {"prompt", "response", "content"} & set(call)
    assert detail["deliverables"]["verdict"]["verdict"] in {
        "APROBADO",
        "APROBADO_CON_OBSERVACIONES",
        "RECHAZADO",
    }
    assert detail["events"][0]["type"] == "run_started"

    events = client.get(f"/api/runs/{run_id}/events").json()
    assert events and events[0]["seq"] == 1
    # El replay parcial (ORQ-17) se apoya en este parámetro.
    resto = client.get(f"/api/runs/{run_id}/events", params={"afterSeq": 1}).json()
    assert [e["seq"] for e in resto] == [e["seq"] for e in events[1:]]

    deliverables = client.get(f"/api/runs/{run_id}/deliverables").json()
    assert "findings" in deliverables and "missing" in deliverables

    page = client.get(f"/api/requirements/{requirement_id}/runs").json()
    assert [r["id"] for r in page["items"]] == [run_id]
    assert page["total"] == 1 and page["offset"] == 0


def test_assisted_plan_is_opt_in(client: TestClient) -> None:
    requirement_id = _create_requirement(client)
    plan = client.post(f"/api/requirements/{requirement_id}/plan", params={"assisted": True}).json()
    # Con el proveedor mock el Orquestador devuelve la misma propuesta que las reglas.
    assert plan["blocked"] is False
    assert {item["source"] for item in plan["plan"]["items"]} <= {"regla", "orquestador"}


def test_cancelling_a_finished_run_returns_400(client: TestClient) -> None:
    requirement_id = _create_requirement(client)
    run_id = client.post(
        f"/api/requirements/{requirement_id}/runs", json={}
    ).json()["id"]
    wait_for_run(client, run_id)
    response = client.post(f"/api/runs/{run_id}/cancel")
    assert response.status_code == 400
    assert client.post("/api/runs/RUN-999/cancel").status_code == 404


def test_blocked_plan_returns_409_with_reasons(client: TestClient) -> None:
    response = client.post(
        "/api/requirements",
        json={"title": "Sin adjuntos", "phi": "si"},
    )
    requirement_id = response.json()["id"]
    run = client.post(f"/api/requirements/{requirement_id}/runs", json={})
    assert run.status_code == 409
    # Forma única de error: código estable, mensaje en español y detalle.
    body = run.json()
    assert body["code"] == "PlanBlockedError"
    assert body["message"]
    assert body["detail"]["reasons"]


def test_unknown_ids_return_404(client: TestClient) -> None:
    response = client.get("/api/requirements/REQ-999")
    assert response.status_code == 404
    assert response.json()["code"] == "NotFoundError"
    assert client.get("/api/runs/RUN-999").status_code == 404
    assert client.get("/api/runs/RUN-999/deliverables").status_code == 404


def test_invalid_body_returns_422(client: TestClient) -> None:
    response = client.post("/api/requirements", json={"owner": "ana"})
    assert response.status_code == 422
    assert response.json()["code"] == "ValidationError"


def test_requirements_are_paginated(client: TestClient) -> None:
    for index in range(3):
        client.post(
            "/api/requirements", json={"title": f"Requerimiento {index}", "owner": "ana"}
        )
    page = client.get("/api/requirements", params={"limit": 2}).json()
    assert len(page["items"]) == 2
    assert page["total"] == 3
    siguiente = client.get("/api/requirements", params={"limit": 2, "offset": 2}).json()
    assert len(siguiente["items"]) == 1
    assert {r["id"] for r in page["items"]} & {r["id"] for r in siguiente["items"]} == set()
