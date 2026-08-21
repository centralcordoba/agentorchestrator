"""MarketDataAgent: único agente que habla con el proveedor de datos.

Responde a:
- TASK_REQUEST {symbol, days}  → TASK_RESULT con resumen de la serie y `data_ref`
- INFO_REQUEST {symbol, days}  → INFO_RESPONSE (historial ampliado pedido por otro agente)
- cualquier fallo              → ERROR {code, reason}
"""
from __future__ import annotations

from ..models import AgentMessage, AgentName, MessageType
from ..providers.market_data_provider import (
    InsufficientDataError,
    MarketDataError,
    SymbolNotFoundError,
)
from .base_agent import BaseAgent


class MarketDataAgent(BaseAgent):
    name = AgentName.MARKET_DATA
    description = "Obtiene y valida precios históricos (OHLCV diario)."

    async def process(self, message: AgentMessage) -> AgentMessage:
        symbol = message.payload.get("symbol") or message.symbol
        days = int(message.payload.get("days") or self.ctx.settings.initial_history_days)
        if not symbol:
            return self.error_reply(message, "Petición sin símbolo.", code="bad_request")

        try:
            series = await self.ctx.market.fetch(symbol, days)
        except SymbolNotFoundError as e:
            return self.error_reply(message, str(e), code="symbol_not_found")
        except InsufficientDataError as e:
            return self.error_reply(message, str(e), code="insufficient_data")
        except MarketDataError as e:
            return self.error_reply(message, str(e), code="provider_error")

        # Validación mínima de integridad: sin cierres negativos ni fechas desordenadas.
        closes = series.closes
        if any(c <= 0 for c in closes):
            return self.error_reply(message, "La serie contiene cierres no positivos.", code="invalid_data")
        dates = [b.date for b in series.bars]
        if dates != sorted(dates):
            return self.error_reply(message, "La serie no está ordenada cronológicamente.", code="invalid_data")

        data_ref = f"{symbol}:{days}"
        self.ctx.data[data_ref] = series
        payload = {
            "data_ref": data_ref,
            "requested_days": days,
            **series.summary(),
            "closes_tail": [round(c, 4) for c in closes[-5:]],
        }
        reply_type = (
            MessageType.INFO_RESPONSE if message.type == MessageType.INFO_REQUEST else MessageType.TASK_RESULT
        )
        return self.reply(message, reply_type, payload)

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        return f"{p.get('bars')} sesiones de {p.get('source')} ({p.get('first_date')} → {p.get('last_date')})"
