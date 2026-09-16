"""Privacidad HIPAA: detección de PHI, redacción y salvaguardas 45 CFR 164.312.

Estas reglas vivían en el navegador (`frontend/lib/rq/privacy.ts`), donde no protegían nada: el
envío al proveedor de LLM ocurre en el servidor. Aquí son dominio puro —solo `re` y `dataclasses`—
y las consultan la pasarela de IA, el motor y los casos de uso.

Tres invariantes que el resto del código da por hechas:

- **El valor nunca sale de aquí.** `Detection` guarda tipo, archivo, línea y dónde apareció. No
  hay ningún campo con el valor detectado, así que no puede acabar en la traza, en la auditoría,
  en un log ni en una respuesta de la API por descuido.
- **Redactar es sustituir, no borrar.** El valor se cambia por un marcador con el tipo
  (`«PHI:ssn»`), de forma que el modelo sigue viendo la forma del código y puede señalar el
  problema sin recibir el dato.
- **Ante la duda, se redacta.** Un valor ficticio conocido (`123-45-6789`) también se sustituye;
  solo rebaja la gravedad del hallazgo, no la redacción.

Las expresiones regulares se escriben con la herramienta de edición, nunca por heredoc de shell:
un `\\b` mal escapado ya dejó una vez un carácter de control dentro de una regex y la dejó
inservible sin que nada fallara.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .enums import AgentId, PhiClassification, PhiIdentifier, PhiWhere, SafeguardId, Severity
from .findings import Finding

#: La PHI aparece asignada en código (`mrn = "…"`) y suelta en prosa (`mrn MRN4471903`), que
#: es como la escribe una persona en la descripción de un requerimiento.
SEP = r"(?:[\"']?\s*[:=]\s*[\"']?|\s+)"

MARKER = "«PHI:{identifier}»"
#: Para no volver a redactar lo ya redactado: una regla amplia puede capturar el marcador que
#: dejó otra más precisa y convertir un «ssn» en un genérico «dato_paciente».
MARKER_RE = re.compile(r"«PHI:[a-z_]+»")


@dataclass(frozen=True, slots=True)
class Safeguard:
    id: SafeguardId
    label: str
    cfr: str
    question: str


SAFEGUARDS: tuple[Safeguard, ...] = (
    Safeguard(
        SafeguardId.ACCESO,
        "Control de acceso",
        "164.312(a)",
        "¿Solo acceden a la PHI los usuarios y procesos autorizados, con cifrado en reposo?",
    ),
    Safeguard(
        SafeguardId.AUDITORIA,
        "Controles de auditoría",
        "164.312(b)",
        "¿Queda registro de quién consulta o modifica PHI?",
    ),
    Safeguard(
        SafeguardId.INTEGRIDAD,
        "Integridad",
        "164.312(c)",
        "¿Se protege la PHI frente a alteraciones o borrados indebidos?",
    ),
    Safeguard(
        SafeguardId.AUTENTICACION,
        "Autenticación",
        "164.312(d)",
        "¿Se verifica la identidad de quien accede a la PHI?",
    ),
    Safeguard(
        SafeguardId.TRANSMISION,
        "Seguridad en la transmisión",
        "164.312(e)",
        "¿La PHI viaja cifrada y por canales seguros?",
    ),
)

IDENTIFIER_LABELS: dict[PhiIdentifier, str] = {
    PhiIdentifier.NOMBRE: "Nombre",
    PhiIdentifier.FECHA: "Fecha de nacimiento",
    PhiIdentifier.TELEFONO: "Teléfono",
    PhiIdentifier.EMAIL: "Email",
    PhiIdentifier.SSN: "SSN",
    PhiIdentifier.HISTORIA_CLINICA: "N.º de historia clínica",
    PhiIdentifier.AFILIADO: "N.º de afiliado / póliza",
    PhiIdentifier.DIRECCION: "Dirección",
    PhiIdentifier.DOCUMENTO: "Documento de identidad",
    PhiIdentifier.DATO_PACIENTE: "Dato de paciente",
}

WHERE_LABELS: dict[PhiWhere, str] = {
    PhiWhere.DATOS_PRUEBA: "datos de prueba",
    PhiWhere.LOG: "logs",
    PhiWhere.SQL: "SQL",
    PhiWhere.CODIGO: "código",
    PhiWhere.URL: "URL",
    PhiWhere.ALMACENAMIENTO_LOCAL: "almacenamiento del navegador",
}


@dataclass(frozen=True, slots=True)
class Detection:
    """Un identificador encontrado. **No lleva el valor**, y no debe llevarlo nunca."""

    identifier: PhiIdentifier
    where: PhiWhere
    file: str = ""
    line: int = 0

    @property
    def masked(self) -> str:
        """Lo único que se puede enseñar o guardar de una detección."""
        return (
            f"{IDENTIFIER_LABELS[self.identifier]} en {WHERE_LABELS[self.where]} · valor oculto"
        )


@dataclass(frozen=True, slots=True)
class ValueRule:
    """Regla que localiza el **valor** de un identificador, para poder sustituirlo.

    El grupo `valor` marca exactamente lo que se redacta: el resto del texto (el nombre del campo,
    la comilla, el operador) se conserva para que el código siga siendo legible.
    """

    identifier: PhiIdentifier
    pattern: re.Pattern[str]
    known_fake: re.Pattern[str] | None = None


#: Estrictas a propósito: una regla laxa («un teléfono son nueve dígitos seguidos»)
#: destrozaría el código que ve el modelo. Las laxas viven en `TYPED_RULES`.
VALUE_RULES: tuple[ValueRule, ...] = (
    ValueRule(
        PhiIdentifier.SSN,
        re.compile(r"(?P<valor>\b\d{3}-\d{2}-\d{4}\b)"),
        re.compile(r"\b(?:000-00-0000|123-45-6789|999-99-9999)\b"),
    ),
    ValueRule(
        PhiIdentifier.HISTORIA_CLINICA,
        re.compile(
            r"\b(?:mrn|medical_?record(?:_?(?:number|no|id))?|historia_?clinica|nhc|expediente)\b"
            + SEP
            + r"(?P<valor>[A-Za-z]*\d{5,})",
            re.IGNORECASE,
        ),
    ),
    ValueRule(
        PhiIdentifier.FECHA,
        re.compile(
            r"\b(?:dob|birth_?date|date_?of_?birth|fecha_?nac\w*)\b"
            + SEP
            + r"(?P<valor>\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
    ),
    ValueRule(
        PhiIdentifier.AFILIADO,
        re.compile(
            r"\b(?:member_?id|policy_?(?:number|no)|insurance_?id|afiliado|p[oó]liza)\b"
            + SEP
            + r"(?P<valor>[A-Z0-9][A-Z0-9-]{5,})",
            re.IGNORECASE,
        ),
    ),
    ValueRule(
        PhiIdentifier.NOMBRE,
        re.compile(
            r"\b(?:patient_?name|nombre_?paciente|patient_?full_?name)\b"
            r"[\"']?\s*[:=]\s*[\"'](?P<valor>[^\"']{3,60})[\"']",
            re.IGNORECASE,
        ),
    ),
    # Un nombre de persona no tiene forma reconocible: solo se detecta cuando la palabra que lo
    # precede dice que lo es. Exige dos palabras capitalizadas para no tragarse «paciente Activo».
    ValueRule(
        PhiIdentifier.NOMBRE,
        re.compile(
            r"\b(?:paciente|patient)\s+"
            r"(?P<valor>[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\b"
        ),
    ),
    ValueRule(
        PhiIdentifier.DATO_PACIENTE,
        re.compile(
            r"[?&](?:ssn|dob|mrn|patient_?id|member_?id|dni|diagnosis)="
            r"(?P<valor>[^&\s\"']+)",
            re.IGNORECASE,
        ),
    ),
    ValueRule(
        PhiIdentifier.EMAIL,
        re.compile(
            r"(?P<valor>[\w.+-]+@(?!ejemplo\.|example\.)[\w-]+\.[a-z]{2,})",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class Redaction:
    """Resultado de redactar un texto."""

    text: str
    detections: tuple[Detection, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.detections)

    @property
    def counts(self) -> dict[PhiIdentifier, int]:
        """Cuántos identificadores de cada tipo se sustituyeron. Métrica sin contenido."""
        return dict(Counter(d.identifier for d in self.detections))


def redact(text: str, *, file: str = "", where: PhiWhere | None = None) -> Redaction:
    """Sustituye los valores de identificador por su marcador.

    Es la función que usa la pasarela de IA: nada sale hacia un proveedor sin pasar por aquí.
    """
    if not text:
        return Redaction(text)

    detections: list[Detection] = []
    result = text
    for rule in VALUE_RULES:
        marker = MARKER.format(identifier=rule.identifier.value)
        # La línea se cuenta sobre el texto que se está sustituyendo ahora, no sobre el original:
        # las reglas anteriores ya cambiaron longitudes.
        source = result

        def replace(
            match: re.Match[str],
            _marker: str = marker,
            _rule: ValueRule = rule,
            _source: str = source,
        ) -> str:
            if MARKER_RE.search(match.group("valor")):
                return match.group(0)  # ya redactado por una regla más precisa
            detections.append(
                Detection(
                    identifier=_rule.identifier,
                    where=where or where_for(file),
                    file=file,
                    line=_line_of(_source, match.start("valor")),
                )
            )
            start, end = match.span("valor")
            return match.group(0)[: start - match.start()] + _marker + match.group(0)[end - match.start() :]

        result = rule.pattern.sub(replace, result)

    return Redaction(result, tuple(detections))


def redact_value(value: object, *, file: str = "") -> tuple[object, tuple[Detection, ...]]:
    """Redacta recursivamente cualquier estructura de contexto (dict, lista, texto).

    El contexto de un agente es un diccionario con listas y textos anidados; redactar solo el
    nivel superior dejaría pasar justo lo que más contenido lleva.
    """
    if isinstance(value, str):
        redaction = redact(value, file=file)
        return redaction.text, redaction.detections
    if isinstance(value, dict):
        out: dict[object, object] = {}
        found: list[Detection] = []
        for key, item in value.items():
            clean, detections = redact_value(item, file=file)
            out[key] = clean
            found.extend(detections)
        return out, tuple(found)
    if isinstance(value, (list, tuple)):
        items: list[object] = []
        found = []
        for item in value:
            clean, detections = redact_value(item, file=file)
            items.append(clean)
            found.extend(detections)
        return (type(value)(items) if isinstance(value, tuple) else items), tuple(found)
    return value, ()


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


TEST_PATH = re.compile(
    r"(^|/)(?:test|tests|__tests__|spec|fixtures?)/|[._-](?:test|spec)\.[a-z]+$",
    re.IGNORECASE,
)
PHI_PATH = re.compile(
    r"(fhir|hl7|patient|paciente|encounter|observation|diagnos|ehr|emr|clinic|medical|health"
    r"|claim|member|afiliad)",
    re.IGNORECASE,
)


def where_for(path: str) -> PhiWhere:
    """Dónde apareció, a partir de la ruta del archivo."""
    if not path:
        return PhiWhere.CODIGO
    if path.lower().endswith(".sql"):
        return PhiWhere.SQL
    return PhiWhere.DATOS_PRUEBA if TEST_PATH.search(path) else PhiWhere.CODIGO


@dataclass(frozen=True, slots=True)
class PracticeRule:
    """Regla que señala una práctica insegura. No hay un valor concreto que sustituir."""

    id: str
    severity: Severity
    safeguard: SafeguardId
    title: str
    detail: str
    suggestion: str
    pattern: re.Pattern[str]
    where: PhiWhere | None = None


PRACTICE_RULES: tuple[PracticeRule, ...] = (
    PracticeRule(
        "PHI-LOG",
        Severity.ALTA,
        SafeguardId.ACCESO,
        "Datos de paciente escritos en logs",
        "Una traza incluye variables con datos de paciente; los logs suelen copiarse a sistemas "
        "sin controles de PHI.",
        "Registrar solo identificadores tokenizados y enmascarar el resto.",
        re.compile(
            r"\b(?:log(?:ger)?|console|System\.out|print)\b[\w.]*\s*\(.*"
            r"\b(?:patient|paciente|ssn|dob|diagnos\w*|mrn|member_?id|afiliado)\b",
            re.IGNORECASE,
        ),
        PhiWhere.LOG,
    ),
    PracticeRule(
        "PHI-URL",
        Severity.ALTA,
        SafeguardId.TRANSMISION,
        "PHI en parámetros de URL",
        "Los parámetros de consulta quedan en logs de servidores, proxies e historial del "
        "navegador.",
        "Enviar esos datos en el cuerpo de una petición POST sobre TLS.",
        re.compile(r"[?&](?:ssn|dob|mrn|patient_?id|member_?id|dni|diagnosis)=", re.IGNORECASE),
        PhiWhere.URL,
    ),
    PracticeRule(
        "PHI-LOCALSTORAGE",
        Severity.ALTA,
        SafeguardId.ACCESO,
        "Datos de paciente guardados en el navegador",
        "localStorage y sessionStorage no están cifrados y los lee cualquier script de la página.",
        "Guardar el borrador en el servidor o cifrarlo con una clave de sesión.",
        re.compile(
            r"(?:localStorage|sessionStorage)\.setItem\(.*"
            r"\b(?:patient|paciente|dni|ssn|dob|phone|telefono|afiliado)\b",
            re.IGNORECASE,
        ),
        PhiWhere.ALMACENAMIENTO_LOCAL,
    ),
    PracticeRule(
        "TLS-OFF",
        Severity.ALTA,
        SafeguardId.TRANSMISION,
        "Verificación TLS desactivada",
        "La conexión acepta certificados no válidos: permite interceptar la PHI en tránsito.",
        "Eliminar la opción y confiar en los certificados de la organización.",
        re.compile(
            r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false"
            r"|InsecureSkipVerify\s*:\s*true|NODE_TLS_REJECT_UNAUTHORIZED"
        ),
    ),
    PracticeRule(
        "HTTP-PLAIN",
        Severity.MEDIA,
        SafeguardId.TRANSMISION,
        "Llamada a un servicio por HTTP sin cifrar",
        "La URL usa http:// fuera de localhost.",
        "Usar https://.",
        re.compile(
            r"[\"'`]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|example\.)[\w.-]+",
            re.IGNORECASE,
        ),
    ),
)

VALUE_SEVERITY: dict[PhiIdentifier, Severity] = {
    PhiIdentifier.SSN: Severity.CRITICA,
    PhiIdentifier.HISTORIA_CLINICA: Severity.CRITICA,
    PhiIdentifier.NOMBRE: Severity.ALTA,
    PhiIdentifier.FECHA: Severity.ALTA,
    PhiIdentifier.AFILIADO: Severity.ALTA,
    PhiIdentifier.DATO_PACIENTE: Severity.ALTA,
    PhiIdentifier.EMAIL: Severity.MEDIA,
}


def analyze_source(file: str, text: str) -> tuple[tuple[Finding, ...], tuple[Detection, ...]]:
    """Revisa un archivo: hallazgos y detecciones, sin quedarse con ningún valor.

    Determinista y sin LLM. El agente de Privacidad la usa como base; el modelo añade el juicio
    que las reglas no pueden dar.
    """
    findings: list[Finding] = []
    detections: list[Detection] = []
    where = where_for(file)
    lines = text.splitlines()

    for rule in VALUE_RULES:
        hits = [
            (number, match)
            for number, line in enumerate(lines, start=1)
            for match in rule.pattern.finditer(line)
        ]
        if not hits:
            continue
        fake = rule.known_fake is not None and all(
            rule.known_fake.search(match.group("valor")) for _, match in hits
        )
        first = hits[0][0]
        label = IDENTIFIER_LABELS[rule.identifier]
        findings.append(
            Finding(
                id=f"PHI-{rule.identifier.value.upper()}-{len(findings) + 1}",
                severity=Severity.BAJA if fake else VALUE_SEVERITY[rule.identifier],
                title=(f"{label} literal (valor de ejemplo conocido)" if fake else f"{label} literal"),
                detail=(
                    f"{len(hits)} aparición(es) en este archivo. El valor no se muestra ni se "
                    "guarda; se sustituye antes de enviarlo a ningún proveedor."
                ),
                source=AgentId.PRIVACY,
                file=file,
                line=first,
                suggestion="Usar datos sintéticos y purgar el historial si el valor era real.",
                safeguard=SafeguardId.ACCESO,
            )
        )
        for number, _ in hits[:5]:
            detections.append(
                Detection(
                    identifier=rule.identifier, where=where, file=file, line=number
                )
            )

    for practice in PRACTICE_RULES:
        hits = [
            number
            for number, line in enumerate(lines, start=1)
            if practice.pattern.search(line)
        ]
        if not hits:
            continue
        findings.append(
            Finding(
                id=f"{practice.id}-{len(findings) + 1}",
                severity=practice.severity,
                title=practice.title,
                detail=(
                    f"{practice.detail}"
                    + (f" {len(hits)} líneas en este archivo." if len(hits) > 1 else "")
                ),
                source=AgentId.PRIVACY,
                file=file,
                line=hits[0],
                suggestion=practice.suggestion,
                safeguard=practice.safeguard,
            )
        )
        if practice.where is not None:
            for number in hits[:5]:
                detections.append(
                    Detection(
                        identifier=PhiIdentifier.DATO_PACIENTE,
                        where=practice.where,
                        file=file,
                        line=number,
                    )
                )

    return tuple(findings), tuple(detections)


def phi_signals(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Rutas cuyo nombre ya sugiere datos de salud. Señal para clasificar, no un hallazgo."""
    seen = [path for path in dict.fromkeys(paths) if PHI_PATH.search(path)]
    return tuple(seen[:8])


#: Más laxas que `VALUE_RULES`: aquí un falso positivo solo produce un aviso.
TYPED_RULES: tuple[tuple[PhiIdentifier, re.Pattern[str]], ...] = (
    (PhiIdentifier.SSN, re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (
        PhiIdentifier.HISTORIA_CLINICA,
        re.compile(
            r"\b(?:mrn|historia\s*cl[ií]nica|nhc|expediente)\b\s*:?\s*[A-Za-z]*\d{4,}",
            re.IGNORECASE,
        ),
    ),
    (
        PhiIdentifier.AFILIADO,
        re.compile(
            r"\b(?:afiliado|p[oó]liza|member\s*id|policy)\b\s*:?\s*[A-Z0-9-]{5,}",
            re.IGNORECASE,
        ),
    ),
    (
        PhiIdentifier.FECHA,
        re.compile(
            r"\b(?:nacid[oa]|fecha\s*de\s*nacimiento|dob)\b\s*:?\s*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}",
            re.IGNORECASE,
        ),
    ),
    (PhiIdentifier.TELEFONO, re.compile(r"\+?\d[\d\s().-]{8,}\d")),
    (
        PhiIdentifier.EMAIL,
        re.compile(r"[\w.+-]+@(?!ejemplo\.|example\.)[\w-]+\.[a-z]{2,}", re.IGNORECASE),
    ),
    (PhiIdentifier.DOCUMENTO, re.compile(r"\b\d{7,8}[A-Za-z]\b")),
)


def scan_typed_text(text: str) -> tuple[PhiIdentifier, ...]:
    """Tipos de identificador que contiene un texto escrito por una persona. Nunca el valor."""
    return tuple(identifier for identifier, pattern in TYPED_RULES if pattern.search(text))


PHI_WORDS: tuple[str, ...] = (
    "paciente",
    "pacientes",
    "historia clínica",
    "diagnóstico",
    "receta",
    "afiliado",
    "aseguradora",
    "copago",
    "laboratorio",
    "clínico",
    "clínica",
    "médico",
    "salud",
    "fhir",
    "hl7",
    "hipaa",
    "phi",
)


def suggest_phi(
    *, title: str, description: str, acceptance_criteria: tuple[str, ...] = (), paths: tuple[str, ...] = ()
) -> tuple[PhiClassification, str]:
    """Sugerencia de clasificación. Nunca decide sola: la persona confirma.

    Ante la falta de señales devuelve `DESCONOCIDO`, que la política trata como «sí».
    """
    signals = phi_signals(paths)
    if signals:
        return (
            PhiClassification.SI,
            f"El cambio toca rutas de datos de salud: {', '.join(signals[:2])}.",
        )

    text = " ".join((title, description, *acceptance_criteria)).lower()
    for word in PHI_WORDS:
        if re.search(rf"(^|[^a-záéíóúüñ]){re.escape(word)}($|[^a-záéíóúüñ])", text):
            return PhiClassification.SI, f"El requerimiento menciona «{word}»."

    return (
        PhiClassification.DESCONOCIDO,
        "No hay señales claras. Mientras no se confirme, se aplica la política de PHI.",
    )
