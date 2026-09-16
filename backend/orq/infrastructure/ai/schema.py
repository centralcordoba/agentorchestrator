"""Validador del subconjunto de JSON Schema que usan los esquemas de salida de los agentes."""
from __future__ import annotations

from typing import Any, Mapping

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
}


def validate(value: Any, schema: Mapping[str, Any], *, path: str = "$") -> list[str]:
    """Devuelve la lista de incumplimientos. Vacía = la salida es válida."""
    errors: list[str] = []

    enum = schema.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"{path}: «{value!r}» no está entre los valores permitidos {list(enum)}.")
        return errors

    expected = schema.get("type")
    if expected is not None:
        python_type = _TYPES.get(expected)
        if python_type is None:
            return errors
        # En JSON, `true` no es un número aunque en Python `bool` herede de `int`.
        if expected in {"number", "integer"} and isinstance(value, bool):
            errors.append(f"{path}: se esperaba {expected} y llegó un booleano.")
            return errors
        if not isinstance(value, python_type):
            errors.append(f"{path}: se esperaba {expected} y llegó {type(value).__name__}.")
            return errors

    if expected == "object" or (expected is None and isinstance(value, dict)):
        errors.extend(_validate_object(value, schema, path))
    elif expected == "array" or (expected is None and isinstance(value, list)):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                errors.extend(validate(item, item_schema, path=f"{path}[{index}]"))

    return errors


def _validate_object(value: dict[str, Any], schema: Mapping[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    properties: Mapping[str, Any] = schema.get("properties") or {}

    for name in schema.get("required") or ():
        if name not in value:
            errors.append(f"{path}: falta la propiedad obligatoria «{name}».")

    if schema.get("additionalProperties") is False:
        for name in value:
            if name not in properties:
                errors.append(f"{path}: propiedad no declarada «{name}».")

    for name, sub_schema in properties.items():
        if name in value and isinstance(sub_schema, Mapping):
            errors.extend(validate(value[name], sub_schema, path=f"{path}.{name}"))

    return errors
