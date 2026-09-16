"""Canal en vivo de una ejecución: replay, reconexión y varios espectadores.

Lo que se comprueba aquí es lo que hace útil al canal: quien llega tarde ve la traza entera,
quien se reconecta no pierde ni repite nada, y dos personas mirando la misma ejecución ven lo
mismo.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from orq.api.container import Container
from orq.application.ports import AgentRequest, AgentResult
from orq.application.use_cases import CreateRequirementCommand, NewAttachment, StartRunCommand
from orq.domain.enums import AgentId, AttachmentKind, PhiClassification
from orq.infrastructure.ai.gateway import AIGateway
from orq.infrastructure.events import InMemoryEventBus, Subscription
from orq.main import create_app

from .conftest import make_user, make_container, run_async


@pytest.fixture
def container(settings) -> Container:
    """Contenedor con bus real: el canal en vivo es lo que se está probando."""
    container = make_container(settings)
    container.events = InMemoryEventBus()
    # El supervisor se construyó con el bus anterior: se recrea con este.
    container.__post_init__()
    return container


@pytest.fixture
def client(container: Container, settings):
    """Cliente con sesión abierta: desde ORQ-5 ninguna ruta de datos responde sin ella."""
    make_user(container)
    with TestClient(create_app(settings, container=container)) as client:
        respuesta = client.post(
            "/api/auth/login",
            json={"email": "ana@acme.test", "password": "contrasena-de-prueba-larga"},
        )
        assert respuesta.status_code == 200, respuesta.text
        yield client


def _create(client: TestClient) -> str:
    response = client.post(
        "/api/requirements",
        json={
            "title": "Conciliación de pagos",
            "description": "Pantalla de pagos y tabla de conciliación.",
            "phi": "no",
            "attachments": [
                {"kind": "repo", "name": "acme/portal"},
                {"kind": "vtr_template", "name": "p.docx"},
            ],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _start(client: TestClient, requirement_id: str) -> str:
    run = client.post(
        f"/api/requirements/{requirement_id}/runs", json={}
    )
    assert run.status_code == 201
    return run.json()["id"]


def _wait_finished(client: TestClient, run_id: str, tries: int = 100) -> None:
    """La ejecución va en segundo plano: se espera a que termine."""
    import time

    for _ in range(tries):
        if client.get(f"/api/runs/{run_id}").json()["run"]["status"] != "en_curso":
            return
        time.sleep(0.05)
    raise AssertionError(f"la ejecución {run_id} no terminó")


def _read_until_end(websocket, limit: int = 300) -> list[dict]:
    """Lee el canal hasta el `end`, descartando los `ping`."""
    frames: list[dict] = []
    for _ in range(limit):
        frame = websocket.receive_json()
        if frame["type"] == "ping":
            continue
        frames.append(frame)
        if frame["type"] == "end":
            return frames
    raise AssertionError("el canal no terminó")


def test_replay_shows_the_whole_trace_even_if_you_arrive_late(client: TestClient) -> None:
    requirement_id = _create(client)
    run_id = _start(client, requirement_id)
    # Con el proveedor mock la ejecución ya terminó cuando abrimos el canal.
    with client.websocket_connect(f"/api/runs/{run_id}/stream") as websocket:
        frames = _read_until_end(websocket)

    assert frames[0]["type"] == "hello"
    assert frames[0]["run"]["id"] == run_id
    events = [f["event"] for f in frames if f["type"] == "event"]
    assert events, "el replay no trajo ningún evento"
    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_completed"
    # Sin huecos ni repetidos: la secuencia es 1..n.
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1))
    assert frames[-1] == {"type": "end", "status": "completada"}


def test_reconnecting_continues_where_it_left_off(client: TestClient) -> None:
    requirement_id = _create(client)
    run_id = _start(client, requirement_id)

    with client.websocket_connect(f"/api/runs/{run_id}/stream") as websocket:
        frames = _read_until_end(websocket)
    events = [f["event"] for f in frames if f["type"] == "event"]
    corte = events[len(events) // 2]["seq"]

    # Reconexión: se pide solo lo posterior a lo último recibido.
    with client.websocket_connect(f"/api/runs/{run_id}/stream?afterSeq={corte}") as websocket:
        frames = _read_until_end(websocket)
    resto = [f["event"] for f in frames if f["type"] == "event"]

    assert [e["seq"] for e in resto] == [e["seq"] for e in events if e["seq"] > corte]
    assert all(e["seq"] > corte for e in resto)  # nada repetido


def test_two_viewers_see_the_same_trace(client: TestClient) -> None:
    requirement_id = _create(client)
    run_id = _start(client, requirement_id)

    with client.websocket_connect(f"/api/runs/{run_id}/stream") as first:
        primeros = _read_until_end(first)
    with client.websocket_connect(f"/api/runs/{run_id}/stream") as second:
        segundos = _read_until_end(second)

    assert [f["event"]["seq"] for f in primeros if f["type"] == "event"] == [
        f["event"]["seq"] for f in segundos if f["type"] == "event"
    ]


def test_unknown_run_closes_the_channel(client: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/runs/RUN-999/stream") as websocket:
            websocket.receive_json()
    assert error.value.code == 4404


def test_channel_closes_cleanly_if_the_last_event_never_arrives(
    client: TestClient, container
) -> None:
    """Rendija entre «la ejecución figura terminada» y «su último evento está guardado».

    El motor marca el estado y justo después emite `run_completed`. Un espectador que conecte en
    medio no puede cerrar sin ese evento (veía la traza incompleta y al reconectar aparecía), ni
    quedarse esperando para siempre si ya no va a llegar. Aquí se fuerza el caso extremo: el
    evento final no existe y el canal tiene que cerrar igualmente, con su `end`.
    """
    requirement_id = _create(client)
    run_id = _start(client, requirement_id)
    _wait_finished(client, run_id)

    guardados = container.runs._events[run_id]
    final = guardados.pop()
    assert final.type.value == "run_completed"

    with client.websocket_connect(f"/api/runs/{run_id}/stream") as websocket:
        frames = _read_until_end(websocket)

    assert frames[-1]["type"] == "end"
    tipos = [f["event"]["type"] for f in frames if f["type"] == "event"]
    assert "run_started" in tipos  # la traza llegó entera hasta donde existía


class _SlowGateway:
    """Deja la ejecución a medias hasta que la prueba la libera."""

    def __init__(self) -> None:
        self._real = AIGateway()
        self.reached_code = asyncio.Event()
        self.release = asyncio.Event()

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        if request.agent_id is AgentId.CODE:
            self.reached_code.set()
            await self.release.wait()
        return await self._real.run_agent(request)


def test_late_viewer_gets_the_replay_and_then_the_live_events(settings) -> None:
    """El caso que importa: abrir la ejecución a mitad de camino."""
    gateway = _SlowGateway()
    container = make_container(settings, gateway=gateway)
    container.events = InMemoryEventBus()
    container.__post_init__()

    async def scenario() -> tuple[list[int], list[int]]:
        requirement = await container.create_requirement()(
            CreateRequirementCommand(
                title="Conciliación",
                description="Pantalla de pagos.",
                owner="ana",
                phi=PhiClassification.NO,
                attachments=(
                    NewAttachment(kind=AttachmentKind.REPO, name="acme/portal"),
                    NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="p.docx"),
                ),
            )
        )
        run = await container.start_run()(
            StartRunCommand(requirement_id=requirement.id, started_by="ana")
        )
        await asyncio.wait_for(gateway.reached_code.wait(), timeout=5)

        # Un espectador llega ahora: se suscribe y luego lee lo ya guardado.
        async with container.events.subscription(run.id) as subscription:
            ya_guardados = [e.seq for e in await container.runs.events(run.id)]
            gateway.release.set()  # la ejecución continúa
            await container.supervisor.wait(run.id)
            en_vivo = [e.seq for e in subscription.drain()]
        return ya_guardados, en_vivo

    replay, live = run_async(scenario())

    assert replay, "el replay debería traer lo emitido antes de conectar"
    assert live, "deberían llegar eventos nuevos tras conectar"
    # Ni huecos ni solapes: el replay termina donde empieza lo vivo.
    nuevos = [seq for seq in live if seq > max(replay)]
    assert nuevos == live
    assert replay + live == list(range(1, len(replay) + len(live) + 1))


def test_a_slow_viewer_does_not_grow_the_server_memory() -> None:
    """Quien no lee pierde eventos, pero no hace crecer la cola sin límite."""
    from orq.infrastructure.events import QUEUE_LIMIT
    from orq.domain.enums import TraceEventType
    from orq.domain.run import TraceEvent
    from datetime import datetime, timezone

    subscription = Subscription("RUN-X")
    for seq in range(QUEUE_LIMIT + 10):
        subscription.offer(
            TraceEvent(
                seq=seq + 1,
                run_id="RUN-X",
                at=datetime.now(timezone.utc),
                type=TraceEventType.LLM_CALL,
            )
        )
    assert subscription.dropped == 10
    assert len(subscription.drain()) == QUEUE_LIMIT
