"""Prueba de arquitectura: la dirección de las dependencias no se invierte.

- `domain` no importa nada del proyecto salvo `domain`, ni framework alguno.
- `application` no importa `infrastructure` ni `api`.
- `infrastructure` no importa `api`.

Se analiza el árbol sintáctico, así que no hace falta importar los módulos.
"""
from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "orq"

#: Frameworks y SDKs que no pueden aparecer en el dominio ni en los casos de uso.
FORBIDDEN_IN_CORE = {"fastapi", "pydantic", "starlette", "anthropic", "httpx", "openai", "sqlalchemy"}


def _modules(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


def _imports(path: Path) -> list[str]:
    """Nombres importados, con los relativos resueltos a `orq.<paquete>`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = path.relative_to(PACKAGE).parts[:-1]
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ("orq", *package_parts[: len(package_parts) - (node.level - 1)])
                names.append(".".join((*base, node.module)) if node.module else ".".join(base))
            elif node.module:
                names.append(node.module)
    return names


def _root(name: str) -> str:
    return name.split(".")[0]


def test_domain_only_depends_on_domain() -> None:
    offenders: list[str] = []
    for path in _modules("domain"):
        for name in _imports(path):
            if _root(name) in FORBIDDEN_IN_CORE:
                offenders.append(f"{path.name} importa {name}")
            if name.startswith("orq.") and not name.startswith("orq.domain"):
                offenders.append(f"{path.name} importa {name}")
    assert not offenders, "El dominio debe ser puro: " + "; ".join(offenders)


def test_application_does_not_depend_on_infrastructure_or_api() -> None:
    offenders: list[str] = []
    for path in _modules("application"):
        for name in _imports(path):
            if _root(name) in FORBIDDEN_IN_CORE:
                offenders.append(f"{path.name} importa {name}")
            if name.startswith("orq.infrastructure") or name.startswith("orq.api"):
                offenders.append(f"{path.name} importa {name}")
    assert not offenders, "Los casos de uso hablan con puertos, no con adaptadores: " + "; ".join(offenders)


def test_infrastructure_does_not_depend_on_api() -> None:
    offenders = [
        f"{path.name} importa {name}"
        for path in _modules("infrastructure")
        for name in _imports(path)
        if name.startswith("orq.api")
    ]
    assert not offenders, "; ".join(offenders)


def test_only_the_ai_layer_talks_to_providers() -> None:
    """Ningún agente ni caso de uso importa un SDK de proveedor."""
    ai_layer = PACKAGE / "infrastructure" / "ai"
    offenders = [
        f"{path.relative_to(PACKAGE)} importa {name}"
        for path in PACKAGE.rglob("*.py")
        if ai_layer not in path.parents
        for name in _imports(path)
        if _root(name) in {"anthropic", "openai"}
    ]
    assert not offenders, "; ".join(offenders)


def test_no_router_reads_a_secret_value() -> None:
    """Ningún router llama a `reveal`: la API no tiene por dónde devolver un valor (ORQ-18).

    Es la contrapartida de que `SecretMetadata` no tenga campo para el valor: aquí se comprueba
    que nadie salta la bóveda llamando directamente al único método que sí lo devuelve.
    """
    culpables = []
    for path in (PACKAGE / "api").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "reveal":
                culpables.append(f"{path.relative_to(PACKAGE)}:{node.lineno} llama a reveal()")

    assert not culpables, "; ".join(culpables)


def test_only_the_vault_and_git_touch_secret_values() -> None:
    """`SecretValue` —lo único que lleva el valor— se queda en su sitio.

    Lo usan la bóveda, el adaptador de credenciales y los puertos que declaran la firma. Si
    aparece en un router o en un caso de uso, es que el valor está viajando de más.
    """
    permitidos = {
        Path("infrastructure/secrets/vault.py"),
        Path("infrastructure/secrets/credentials.py"),
        Path("application/ports.py"),
        Path("domain/secrets.py"),
    }
    culpables = [
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if path.relative_to(PACKAGE) not in permitidos
        and "SecretValue" in path.read_text(encoding="utf-8")
    ]

    assert not culpables, "SecretValue aparece fuera de la bóveda: " + ", ".join(culpables)


def test_only_the_login_reads_a_password_hash() -> None:
    """El hash de la contraseña solo lo toca quien lo necesita (ORQ-5).

    `User` no tiene campo de contraseña, así que no puede filtrarse por una respuesta; esto
    comprueba lo otro: que nadie salte esa protección llamando al repositorio directamente.
    """
    permitidos = {
        Path("application/auth.py"),  # login y cambio de contraseña
        Path("application/ports.py"),  # declara la firma
        Path("infrastructure/auth/repository.py"),  # la implementa
        Path("api/container.py"),  # siembra la cuenta inicial
        Path("infrastructure/db/schema.py"),  # declara la columna
    }
    culpables = [
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if path.relative_to(PACKAGE) not in permitidos
        and ("credential_of" in path.read_text(encoding="utf-8")
             or "password_hash" in path.read_text(encoding="utf-8"))
    ]

    assert not culpables, "el hash de la contraseña se toca fuera de su sitio: " + ", ".join(culpables)


def test_no_router_builds_an_actor_from_the_request_body() -> None:
    """El actor de una acción sale de la sesión, nunca del cuerpo (ORQ-5).

    Si alguien vuelve a añadir un `by` o un `startedBy` al cuerpo de una petición, esta prueba lo
    caza: la auditoría dejaría de valer como registro de quién hizo qué.
    """
    culpables = []
    for path in (PACKAGE / "api" / "routers").rglob("*.py"):
        texto = path.read_text(encoding="utf-8")
        for patron in ("by=body.by", "by=body.started_by", "started_by=body.", "owner=body.owner"):
            if patron in texto:
                culpables.append(f"{path.name}: {patron}")

    assert not culpables, "; ".join(culpables)
