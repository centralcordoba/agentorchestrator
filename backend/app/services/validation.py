"""Validación de entradas y de salidas del LLM.

La regla central de la demo es "no inventar datos": cualquier número que aparezca
en un texto generado por el LLM debe existir en los hechos que se le entregaron, y
cualquier evidencia citada debe referirse a un hecho real. Si no es así, el texto se
descarta (se usa el generado por reglas) y la incidencia queda en la traza.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from ..models import LLMExplanation

SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")
NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
# Porcentajes: "80 %", "−12,5%"... nunca se eximen del anclaje (un "80%" inventado es una afirmación fuerte).
PERCENT_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*%")


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


# ----------------------------------------------------------------- números anclados
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
    elif isinstance(obj, str):
        # Números incrustados en cadenas de los hechos (p. ej. fechas "2026-08-21") también cuentan.
        for raw in NUMBER_RE.findall(obj):
            try:
                out.append(float(raw.replace(",", ".")))
            except ValueError:
                pass


def _number_is_grounded(n: float, facts_numbers: list[float], *, allow_small_int: bool = True) -> bool:
    """Un número está 'anclado' si coincide (con redondeo) con algún hecho, con su
    versión en porcentaje (x100) o con enteros pequeños usados como cantidades."""
    if allow_small_int and abs(n) <= 100 and float(n).is_integer():
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


def ungrounded_numbers(text: str, facts: dict[str, Any]) -> list[str]:
    facts_numbers: list[float] = []
    _flatten_numbers(facts, facts_numbers)
    bad: list[str] = []
    text = text or ""
    # 1) porcentajes: se comprueban sin la exención de enteros pequeños y se retiran del texto
    for raw in PERCENT_RE.findall(text):
        try:
            n = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not _number_is_grounded(n, facts_numbers, allow_small_int=False):
            bad.append(f"{raw}%")
    remaining = PERCENT_RE.sub(" ", text)
    # 2) resto de números
    for raw in NUMBER_RE.findall(remaining):
        try:
            n = float(raw.replace(",", "."))
        except ValueError:
            continue
        if not _number_is_grounded(n, facts_numbers):
            bad.append(raw)
    return bad


# ------------------------------------------------------------ modo reglas (resumen)
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

    for raw in ungrounded_numbers(summary, facts):
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


# ------------------------------------------------------------- modo llm (agentes)
def validate_agent_output(
    output: dict[str, Any],
    known_facts: dict[str, Any],
    *,
    enum_fields: Optional[dict[str, list[str]]] = None,
    bool_fields: Iterable[str] = (),
    text_fields: Iterable[str] = ("summary",),
    list_fields: Iterable[str] = ("caveats",),
    confidence_field: Optional[str] = "confidence",
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Limpia y valida la salida estructurada de un agente en modo llm.

    Devuelve (clean, warnings, hard_errors). Un `hard_error` significa que la salida no es
    utilizable (p. ej. postura fuera del enumerado) y el agente debe caer al modo reglas.
    Los textos con números no anclados se marcan en `clean["_ungrounded"][campo]` para que el
    agente los sustituya por un texto generado a partir de la evidencia.
    """
    clean: dict[str, Any] = {}
    warnings: list[str] = []
    hard: list[str] = []

    for field_name, allowed in (enum_fields or {}).items():
        val = output.get(field_name)
        if isinstance(val, str):
            val = val.strip().upper() if allowed and allowed[0].isupper() else val.strip()
        if val not in allowed:
            hard.append(f"Campo '{field_name}' fuera del enumerado: {val!r}.")
        clean[field_name] = val

    for field_name in bool_fields:
        val = output.get(field_name)
        if not isinstance(val, bool):
            warnings.append(f"Campo '{field_name}' no booleano ({val!r}); se interpreta como False.")
            val = False
        clean[field_name] = val

    if confidence_field:
        raw_conf = output.get(confidence_field, 0.5)
        try:
            conf = float(raw_conf)
        except (TypeError, ValueError):
            warnings.append(f"Confianza no numérica ({raw_conf!r}); se usa 0.5.")
            conf = 0.5
        if conf < 0 or conf > 1:
            warnings.append(f"Confianza fuera de [0, 1] ({conf}); se acota.")
            conf = min(1.0, max(0.0, conf))
        clean[confidence_field] = round(conf, 2)

    evidence_in = output.get("evidence")
    if isinstance(evidence_in, list):
        evidence: list[dict[str, str]] = []
        for item in evidence_in:
            if not isinstance(item, dict):
                continue
            fact = str(item.get("fact", "")).strip()
            observation = str(item.get("observation", "")).strip()[:300]
            if fact in known_facts:
                evidence.append({"fact": fact, "observation": observation})
            else:
                warnings.append(f"Evidencia sobre un hecho inexistente: '{fact}'.")
        clean["evidence"] = evidence

    clean["_ungrounded"] = {}
    for field_name in text_fields:
        text = str(output.get(field_name, "") or "").strip()
        if len(text) > 900:
            text = text[:900] + "…"
        bad = ungrounded_numbers(text, known_facts)
        if bad:
            warnings.append(f"'{field_name}' contiene números ausentes de los hechos: {', '.join(bad)}.")
            clean["_ungrounded"][field_name] = bad
        clean[field_name] = text

    for field_name in list_fields:
        raw_list = output.get(field_name) or []
        if not isinstance(raw_list, list):
            raw_list = []
        clean[field_name] = [str(x).strip()[:300] for x in raw_list if isinstance(x, (str, int, float))][:6]

    return clean, warnings, hard


def evidence_summary(lead: str, evidence: list[dict[str, str]], known_facts: dict[str, Any]) -> str:
    """Texto de respaldo construido solo con evidencia validada (sin números inventados)."""
    parts = []
    for e in evidence[:4]:
        value = known_facts.get(e["fact"])
        parts.append(f"{e['fact']} = {value}" if not isinstance(value, (dict, list)) else e["fact"])
    return f"{lead} Evidencia: {'; '.join(parts) if parts else 'sin evidencia citada'}."
