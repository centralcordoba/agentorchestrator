"""API FastAPI de la demo educativa multiagente.

Endpoints:
- POST /api/runs                 → crea y lanza una ejecución
- GET  /api/runs                 → lista ejecuciones
- GET  /api/runs/{run_id}        → resumen y resultados
- GET  /api/runs/{run_id}/events → eventos (para replay / auditoría)
- WS   /ws/runs/{run_id}         → eventos en tiempo real (con replay inicial)
- GET  /api/health, /api/config, /api/agents
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .events import EventBus
from .models import DISCLAIMER, AgentMode, RunCreated, RunRequest, RunStatus, RunSummary, new_id, now
from .orchestrator import Orchestrator
from .providers.llm_provider import LLMProvider, ThrottledLLMProvider
from .providers.market_data_provider import MarketDataProvider
from .providers.mock_llm_provider import MockLLMProvider
from .providers.mock_market_data_provider import MockMarketDataProvider
from .services.run_store import RunStore
from .services.validation import normalize_symbols
from .websocket_manager import WebSocketManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # una línea por petición LLM es demasiado ruido
logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # los símbolos inexistentes ya se reportan en la traza
log = logging.getLogger("app")

store = RunStore(persist_dir=settings.runs_dir or None)
ws_manager = WebSocketManager()
bus = EventBus(store, ws_manager)
_background: set[asyncio.Task] = set()


def build_llm_provider() -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from .providers.anthropic_provider import AnthropicProvider

        return ThrottledLLMProvider(AnthropicProvider(), settings.llm_max_concurrency)
    if settings.llm_provider == "openrouter":
        from .providers.openrouter_provider import OpenRouterProvider

        return ThrottledLLMProvider(OpenRouterProvider(), settings.llm_max_concurrency)
    if settings.llm_provider != "mock":
        log.warning("LLM_PROVIDER=%r desconocido; se usa 'mock'.", settings.llm_provider)
    return MockLLMProvider()


def build_market_provider() -> MarketDataProvider:
    if settings.market_data_provider == "yfinance":
        from .providers.yfinance_provider import YFinanceProvider

        return YFinanceProvider()
    return MockMarketDataProvider()


llm_provider: LLMProvider
market_provider: MarketDataProvider


@asynccontextmanager
async def lifespan(_: FastAPI):
    global llm_provider, market_provider
    llm_provider = build_llm_provider()
    market_provider = build_market_provider()
    log.info("LLM provider: %s | Market data provider: %s", llm_provider.name, market_provider.name)
    yield
    for task in list(_background):
        task.cancel()


app = FastAPI(
    title="Demo educativa multiagente",
    description=DISCLAIMER,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "disclaimer": DISCLAIMER}


@app.get("/api/config")
async def config() -> dict:
    return {
        "llm_provider": llm_provider.name,
        "market_data_provider": market_provider.name,
        "max_symbols_per_run": settings.max_symbols_per_run,
        "max_parallel_symbols": settings.max_parallel_symbols,
        "demo_delay_ms": settings.demo_delay_ms,
        "message_delay_ms": settings.message_delay_ms,
        "max_message_delay_ms": settings.max_message_delay_ms,
        "agent_mode": settings.agent_mode if settings.agent_mode in ("rules", "llm") else "rules",
        "llm_supports_tools": llm_provider.supports_tools,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/agents")
async def agents() -> list[dict]:
    from .agents.decision_agent import DecisionAgent
    from .agents.market_data_agent import MarketDataAgent
    from .agents.risk_agent import RiskAgent
    from .agents.skeptic_agent import SkepticAgent
    from .agents.technical_agent import TechnicalAgent

    return [
        {"name": "orchestrator", "description": "Inicia la ejecución, enruta mensajes y agrega resultados."},
        *(
            {"name": cls.name.value, "description": cls.description}
            for cls in (MarketDataAgent, TechnicalAgent, RiskAgent, SkepticAgent, DecisionAgent)
        ),
    ]


@app.post("/api/runs", response_model=RunCreated, status_code=202)
async def create_run(req: RunRequest) -> RunCreated:
    symbols, rejected = normalize_symbols(req.symbols, settings.max_symbols_per_run)
    if not symbols:
        raise HTTPException(status_code=422, detail={"message": "Ningún símbolo válido.", "rejected": rejected})

    run_id = new_id("run")
    orchestrator = Orchestrator(
        run_id=run_id,
        symbols=symbols,
        bus=bus,
        store=store,
        llm=llm_provider,
        market=market_provider,
        settings=settings,
        message_delay_ms=req.message_delay_ms,
        agent_mode=req.agent_mode.value if req.agent_mode else None,
    )
    store.create(
        RunSummary(
            run_id=run_id,
            status=RunStatus.PENDING,
            symbols=symbols,
            created_at=now(),
            providers={"llm": llm_provider.name, "market_data": market_provider.name},
            message_delay_ms=orchestrator.message_delay_ms,
            agent_mode=AgentMode(orchestrator.agent_mode),
        )
    )

    async def _run() -> None:
        try:
            await orchestrator.run()
        except Exception:
            log.exception("La ejecución %s falló", run_id)
            store.set_status(run_id, RunStatus.FAILED)

    task = asyncio.create_task(_run())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return RunCreated(run_id=run_id, symbols=symbols, rejected=rejected, message_delay_ms=orchestrator.message_delay_ms, agent_mode=AgentMode(orchestrator.agent_mode))


@app.get("/api/runs", response_model=list[RunSummary])
async def list_runs() -> list[RunSummary]:
    return store.list()


@app.get("/api/runs/{run_id}", response_model=RunSummary)
async def get_run(run_id: str) -> RunSummary:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")
    return run


@app.get("/api/runs/{run_id}/costs")
async def get_costs(run_id: str) -> dict:
    """Consumo LLM por agente (tokens y USD). Se calcula en vivo a partir de la traza."""
    if store.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")
    from .services.costs import summarize_costs

    return summarize_costs(store.events(run_id)).model_dump(mode="json")


@app.get("/api/runs/{run_id}/events")
async def get_events(run_id: str, after: int = 0) -> list[dict]:
    if store.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada.")
    return [e.model_dump(mode="json") for e in store.events(run_id, after_seq=after)]


@app.websocket("/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    if store.get(run_id) is None:
        await websocket.close(code=4004, reason="Ejecución no encontrada.")
        return
    await ws_manager.connect(run_id, websocket)
    try:
        # Replay: el cliente recibe primero todo lo ocurrido hasta ahora, luego lo nuevo.
        for event in store.events(run_id):
            await ws_manager.send_event(websocket, event)
        while True:
            # Mantener la conexión viva; el cliente puede enviar "ping".
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(run_id, websocket)


# --------------------------------------------------------------------------- frontend estático
# Modo "un solo proceso": si existe el build estático del frontend (npm run build:static),
# se sirve desde aquí y la demo completa queda en http://localhost:8000 sin Node ni Docker.
# Debe montarse al final para que las rutas /api y /ws tengan prioridad.
if os.path.isdir(settings.frontend_dist) and os.path.isfile(os.path.join(settings.frontend_dist, "index.html")):
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    log.info("Sirviendo frontend estático desde %s", settings.frontend_dist)
else:
    log.info("Sin frontend estático en %s (usa `npm run dev` o `build:static`).", settings.frontend_dist)
