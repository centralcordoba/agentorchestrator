"""Validación de entradas y de salidas del LLM.

La regla central de la demo es "no inventar datos": cualquier número que aparezca
en una explicación generada por el LLM debe existir en los hechos que se le
entregaron. Si no es así, la explicación se descarta y se usa la generada por reglas.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from ..models import LLMExplanation

SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")
NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def normalize_symbols(raw: Iterable[str], max_symbols: int) -> tuple[list[str], dict[str, str]]:
    accepted: list[str] = []
    rejected: dict[str, str] = {}
    for item in raw:
        sym = (item or "").strip().upper()
        if not sym:
            continue
        if not SYMBOL_RE.match(sym):
            rejected[sym] = "Formato de símbolo no válido (use letras, dígitos, '.' o '-')."
            continue
        if sym in accepted:
            rejected[sym] = "Símbolo duplicado."
            continue
        if len(accepted) >= max_symbols:
            rejected[sym] = f"Se supera el máximo de {max_symbols} símbolos por ejecución."
            continue
        accepted.append(sym)
    return accepted, rejected


def _flatten_numbers(obj: Any, out: list[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_numbers(v, out)


def _number_is_grounded(n: float, facts_numbers: list[float]) -> bool:
    """Un número está 'anclado' si coincide (con redondeo) con algún hecho, con su
    versión en porcentaje (x100) o con enteros pequeños usados como cantidades."""
    if abs(n) <= 100 and float(n).is_integer():
        # Periodos (14, 20, 50), conteos, umbrales clásicos (30/70)...
        return True
    for f in facts_numbers:
        for candidate in (f, f * 100):
            for digits in (0, 1, 2, 3):
                if round(candidate, digits) == round(n, digits):
                    return True
            if candidate != 0 and abs(candidate - n) / abs(candidate) < 0.006:
                return True
    return False


def validate_explanation(output: dict[str, Any], facts: dict[str, Any], provider_name: str) -> tuple[LLMExplanation, list[str]]:
    warnings: list[str] = []
    summary = str(output.get("summary", "")).strip()
    if not summary:
        warnings.append("El LLM devolvió un resumen vacío.")
    if len(summary) > 900:
        warnings.append("Resumen demasiado largo; se ha truncado.")
        summary = summary[:900] + "…"

    facts_used = [str(f) for f in output.get("facts_used", []) if isinstance(f, str)]
    unknown = [f for f in facts_used if f not in facts]
    if unknown:
        warnings.append(f"El LLM citó hechos inexistentes: {', '.join(unknown)}.")
        facts_used = [f for f in facts_used if f in facts]

    facts_numbers: list[float] = []
    _flatten_numbers(facts, facts_numbers)
    for raw in NUMBER_RE.findall(summary):
        try:
            n = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not _number_is_grounded(n, facts_numbers):
            warnings.append(f"El número '{raw}' del resumen no aparece en los hechos proporcionados.")

    caveats = [str(c) for c in output.get("caveats", []) if isinstance(c, str)][:5]
    explanation = LLMExplanation(
        summary=summary,
        facts_used=facts_used,
        caveats=caveats,
        generated_by=provider_name,
        validation_warnings=warnings,
    )
    return explanation, warnings
