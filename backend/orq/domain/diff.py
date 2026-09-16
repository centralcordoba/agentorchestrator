"""Diff unificado: lectura, mapa del cambio y utilidades que consumen los agentes."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .enums import FileStatus
from .findings import ChangeMapEntry

#: Cabecera de hunk: `@@ -12,7 +12,9 @@`. El número que importa es el del archivo nuevo.
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True, slots=True)
class DiffLine:
    """Una línea añadida, con su número en la versión nueva del archivo."""

    line: int
    text: str


@dataclass(frozen=True, slots=True)
class FileDiff:
    """Un archivo del diff. `patch` son solo los hunks, sin la cabecera de git."""

    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    patch: str = ""
    old_path: str = ""
    binary: bool = False

    @property
    def has_patch(self) -> bool:
        return bool(self.patch)

    @property
    def size(self) -> int:
        return self.additions + self.deletions


def added_lines(patch: str) -> tuple[DiffLine, ...]:
    """Líneas añadidas con su número de línea en la versión nueva.

    Las reglas deterministas trabajan **solo sobre lo añadido**: revisar lo que ya estaba sería
    revisar el repositorio entero, no el cambio.
    """
    out: list[DiffLine] = []
    number = 0
    for raw in patch.split("\n"):
        header = HUNK.match(raw)
        if header:
            number = int(header.group(1))
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            out.append(DiffLine(number, raw[1:]))
            number += 1
        elif raw.startswith(" ") or not raw:
            number += 1
    return tuple(out)


_DIFF_HEADER = re.compile(r'^diff --git "?a/(?P<a>.+?)"? "?b/(?P<b>.+?)"?$')


def parse_diff(text: str) -> tuple[FileDiff, ...]:
    """Lee la salida de `git diff` y la parte en archivos.

    Se apoya en `diff --git` como separador, no en los `---`/`+++`: un archivo binario o un
    renombrado sin cambios no los trae, y perderlos dejaría archivos fuera del inventario.
    """
    files: list[FileDiff] = []
    current: list[str] = []

    def cerrar() -> None:
        if current:
            parsed = _parse_file(current)
            if parsed is not None:
                files.append(parsed)
            current.clear()

    for line in text.split("\n"):
        if line.startswith("diff --git "):
            cerrar()
        current.append(line)
    cerrar()
    return tuple(files)


def _parse_file(block: list[str]) -> FileDiff | None:
    header = _DIFF_HEADER.match(block[0]) if block else None
    if header is None:
        return None

    path = header.group("b")
    old_path = header.group("a")
    status = FileStatus.MODIFIED
    binary = False
    hunks: list[str] = []
    in_hunk = False

    for line in block[1:]:
        if line.startswith("new file mode"):
            status = FileStatus.ADDED
        elif line.startswith("deleted file mode"):
            status = FileStatus.REMOVED
        elif line.startswith("rename to "):
            status = FileStatus.RENAMED
            path = line[len("rename to ") :].strip()
        elif line.startswith("rename from "):
            old_path = line[len("rename from ") :].strip()
        elif line.startswith("Binary files "):
            binary = True
        elif line.startswith("@@"):
            in_hunk = True
            hunks.append(line)
        elif in_hunk:
            hunks.append(line)

    patch = "\n".join(hunks)
    additions = sum(1 for l in hunks if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in hunks if l.startswith("-") and not l.startswith("---"))
    return FileDiff(
        path=path,
        status=status,
        additions=additions,
        deletions=deletions,
        patch=patch,
        old_path=old_path if old_path != path else "",
        binary=binary,
    )


#: Si un archivo no encaja en ninguna, el mapa lo lista igual pero sin símbolos.
SYMBOL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:async\s+)?def\s+(?P<name>\w+)"),  # python
    re.compile(r"^\s*class\s+(?P<name>\w+)"),  # python, java, c#, kotlin…
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)"),  # js/ts
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s*)?\("),
    re.compile(r"^\s*(?:public|private|protected|internal)\s+[\w<>\[\],\s]+\s(?P<name>\w+)\s*\("),
    re.compile(r"^\s*(?:func|fn|sub)\s+(?P<name>\w+)"),  # go, rust, vb
    re.compile(r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|PROCEDURE|FUNCTION)\s+[\"\[]?(?P<name>[\w.]+)", re.IGNORECASE),
)

STOPWORDS: frozenset[str] = frozenset(
    """el la los las un una unos unas de del al a en y o que se su sus por para con sin sobre
    entre como cuando donde es son ser esta este esto estos estas lleva debe puede tiene hay
    the of and to in for with that this it is are be""".split()
)


CHANGE_LABEL: dict[FileStatus, str] = {
    FileStatus.ADDED: "nuevo",
    FileStatus.MODIFIED: "modificado",
    FileStatus.REMOVED: "eliminado",
    FileStatus.RENAMED: "renombrado",
}


def symbols_of(file: FileDiff, limit: int = 8) -> tuple[str, ...]:
    """Funciones, clases y tablas que aparecen en lo añadido."""
    found: list[str] = []
    for line in added_lines(file.patch):
        for pattern in SYMBOL_PATTERNS:
            match = pattern.match(line.text)
            if match:
                name = match.group("name")
                if name not in found:
                    found.append(name)
                break
    return tuple(found[:limit])


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-záéíóúñ]{4,}", text.lower()) if w not in STOPWORDS}


def _path_words(path: str) -> set[str]:
    # `portal/pagos/ConciliacionService.java` → {portal, pagos, conciliacion, service}
    partes = re.split(r"[/\\._-]|(?<=[a-z])(?=[A-Z])", path)
    return _words(" ".join(partes))


def matching_criteria(file: FileDiff, criteria: tuple[str, ...]) -> tuple[int, ...]:
    """Criterios que el archivo parece cubrir, por coincidencia de palabras.

    Es una pista, no una afirmación: el mapa dice «este archivo se parece a este criterio» y es
    el agente quien lo confirma. Por eso basta con una palabra significativa en común.
    """
    vocabulario = _path_words(file.path) | _words(
        " ".join(line.text for line in added_lines(file.patch)[:200])
    )
    return tuple(
        index
        for index, criterion in enumerate(criteria)
        if _words(criterion) & vocabulario
    )


def change_map(
    files: tuple[FileDiff, ...], criteria: tuple[str, ...] = ()
) -> tuple[ChangeMapEntry, ...]:
    """Mapa del cambio determinista: lo que consumen todos los demás agentes."""
    return tuple(
        ChangeMapEntry(
            file=f.path,
            change=CHANGE_LABEL[f.status],
            added=f.additions,
            removed=f.deletions,
            symbols=symbols_of(f),
            criteria=matching_criteria(f, criteria),
        )
        for f in files
    )


def uncovered_criteria(
    entries: tuple[ChangeMapEntry, ...], criteria: tuple[str, ...]
) -> tuple[int, ...]:
    """Criterios a los que no apunta ningún archivo. Señal para el agente, no un veredicto."""
    cubiertos = {index for entry in entries for index in entry.criteria}
    return tuple(i for i in range(len(criteria)) if i not in cubiertos)
