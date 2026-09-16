"""Guardarraíl de PHI: detección, redacción y lo que nunca puede salir (ORQ-20).

La prueba que más importa es la de extremo a extremo: se siembra PHI sintética en todo lo que
viaja (descripción, criterios, adjuntos y el resultado de una herramienta), se ejecuta la revisión
entera y se comprueba que **ningún valor** aparece en lo que recibió el proveedor, ni en la traza,
ni en la auditoría.
"""
from __future__ import annotations

from typing import Any

import pytest

from orq.application.ports import AgentRequest, ToolSpec
from orq.application.use_cases import CreateRequirementCommand, NewAttachment, StartRunCommand
from orq.domain.enums import (
    AgentId,
    AttachmentKind,
    PhiClassification,
    PhiIdentifier,
    PhiWhere,
    ProviderId,
    RunStatus,
    Severity,
)
from orq.domain.errors import PolicyViolationError
from orq.domain.policies import check_agent_provider
from orq.domain.privacy import (
    analyze_source,
    phi_signals,
    redact,
    redact_value,
    scan_typed_text,
    suggest_phi,
    where_for,
)
from orq.domain.profiles import ProfileSnapshot
from orq.infrastructure.ai.gateway import AIGateway
from orq.infrastructure.ai.providers import MockLLMProvider, ProviderRequest, ProviderResponse

from .conftest import make_container, run_async

# PHI sintética. Valores inventados con formato válido: ninguno corresponde a una persona.
SSN = "412-88-7301"
MRN = "MRN4471903"
DOB = "1968-04-23"
MEMBER = "AET-773911-K"
NAME = "Lucia Ferrer Blanco"
EMAIL = "lucia.ferrer@hospital-norte.es"
VALORES = (SSN, MRN, DOB, MEMBER, NAME, EMAIL)

CODIGO_CON_PHI = f"""class Paciente:
    ssn = "{SSN}"
    mrn = "{MRN}"
    dob = "{DOB}"
    member_id = "{MEMBER}"
    patient_name = "{NAME}"
    contacto = "{EMAIL}"
    url = "https://api.interno/historia?ssn={SSN}"
"""


@pytest.mark.parametrize(
    ("texto", "identifier"),
    [
        (f'ssn = "{SSN}"', PhiIdentifier.SSN),
        (f'mrn: "{MRN}"', PhiIdentifier.HISTORIA_CLINICA),
        (f'medical_record_number = "{MRN}"', PhiIdentifier.HISTORIA_CLINICA),
        (f'dob = "{DOB}"', PhiIdentifier.FECHA),
        (f'date_of_birth: "{DOB}"', PhiIdentifier.FECHA),
        (f'member_id = "{MEMBER}"', PhiIdentifier.AFILIADO),
        (f'policy_number: "{MEMBER}"', PhiIdentifier.AFILIADO),
        (f'patient_name = "{NAME}"', PhiIdentifier.NOMBRE),
        (f'correo = "{EMAIL}"', PhiIdentifier.EMAIL),
        ("/historia?patient_id=99120334&x=1", PhiIdentifier.DATO_PACIENTE),
        (f"ssn {SSN} del alta", PhiIdentifier.SSN),
        (f"mrn {MRN} en el informe", PhiIdentifier.HISTORIA_CLINICA),
        (f"dob {DOB}", PhiIdentifier.FECHA),
        (f"El paciente {NAME} reclama", PhiIdentifier.NOMBRE),
    ],
)
def test_each_identifier_is_detected_and_replaced(texto: str, identifier: PhiIdentifier) -> None:
    redaction = redact(texto)

    assert identifier in redaction.counts, f"no se detectó {identifier.value} en: {texto}"
    assert f"«PHI:{identifier.value}»" in redaction.text
    for valor in VALORES:
        assert valor not in redaction.text


@pytest.mark.parametrize(
    "texto",
    [
        "version = '1.2.3'",
        "timeout = 30",
        "fecha_alta = '2026-01-15'",  # una fecha suelta no es una fecha de nacimiento
        "código de país +34",
        'correo = "soporte@example.com"',  # dominio de ejemplo: no es un contacto real
        'correo = "info@ejemplo.org"',
        "member_count = 12",  # nombre parecido, valor que no tiene forma de identificador
        "-- 123 --",
    ],
)
def test_ordinary_code_is_left_alone(texto: str) -> None:
    """Una regla laxa destrozaría el código que ve el modelo: estos casos no se tocan."""
    redaction = redact(texto)

    assert redaction.text == texto
    assert redaction.detections == ()


def test_a_detection_has_no_field_for_the_value() -> None:
    """La garantía es estructural: no hay dónde guardar el valor, así que no puede escaparse."""
    redaction = redact(f'ssn = "{SSN}"', file="src/paciente.py")
    detection = redaction.detections[0]

    assert set(detection.__slots__) == {"identifier", "where", "file", "line"}
    assert SSN not in detection.masked
    assert detection.masked == "SSN en código · valor oculto"


def test_the_marker_is_not_redacted_twice() -> None:
    """Una regla amplia no debe convertir el «ssn» que dejó otra en un genérico."""
    redaction = redact(f'url = "/historia?ssn={SSN}"')

    assert redaction.counts == {PhiIdentifier.SSN: 1}


def test_line_and_file_point_to_the_right_place() -> None:
    redaction = redact(CODIGO_CON_PHI, file="src/paciente.py")
    primera = {}
    for detection in redaction.detections:
        primera.setdefault(detection.identifier, detection)

    assert primera[PhiIdentifier.SSN].line == 2
    assert primera[PhiIdentifier.HISTORIA_CLINICA].line == 3
    assert all(d.file == "src/paciente.py" for d in redaction.detections)
    assert all(d.where is PhiWhere.CODIGO for d in redaction.detections)


def test_where_depends_on_the_path() -> None:
    assert where_for("tests/fixtures/pacientes.py") is PhiWhere.DATOS_PRUEBA
    assert where_for("db/migracion.sql") is PhiWhere.SQL
    assert where_for("src/app/paciente_service.py") is PhiWhere.CODIGO


def test_nested_context_is_redacted_too() -> None:
    """El contexto de un agente son listas y diccionarios anidados, no un texto plano."""
    contexto = {
        "description": f"El paciente {NAME} con SSN {SSN}",
        "acceptance_criteria": [f"Buscar por mrn = {MRN}", "Sin cambios visibles"],
        "attachments": [{"kind": "repo", "detail": f"contacto {EMAIL}"}],
        "count": 3,
    }

    limpio, detections = redact_value(contexto)

    assert SSN not in str(limpio)
    assert EMAIL not in str(limpio)
    assert limpio["count"] == 3
    assert {d.identifier for d in detections} >= {PhiIdentifier.SSN, PhiIdentifier.EMAIL}


def test_analysis_reports_findings_without_the_value() -> None:
    findings, detections = analyze_source("src/paciente.py", CODIGO_CON_PHI)

    assert findings
    assert any(f.severity is Severity.CRITICA for f in findings)
    assert all(f.source is AgentId.PRIVACY for f in findings)
    texto = " ".join(f"{f.title} {f.detail} {f.suggestion}" for f in findings)
    for valor in VALORES:
        assert valor not in texto
    assert all(d.file == "src/paciente.py" for d in detections)


def test_a_known_example_value_is_still_redacted_but_weighs_less() -> None:
    codigo = 'ssn = "123-45-6789"'

    findings, _ = analyze_source("tests/datos.py", codigo)
    ssn = next(f for f in findings if "SSN" in f.title)

    assert ssn.severity is Severity.BAJA
    assert "«PHI:ssn»" in redact(codigo).text  # se redacta igual: ante la duda, se sustituye


def test_unsafe_practices_are_reported() -> None:
    codigo = (
        'logger.info("paciente %s ssn %s", patient, ssn)\n'
        "requests.get(url, verify=False)\n"
        'localStorage.setItem("paciente", JSON.stringify(datos))\n'
    )

    findings, _ = analyze_source("src/app.js", codigo)
    ids = {f.title for f in findings}

    assert "Datos de paciente escritos en logs" in ids
    assert "Verificación TLS desactivada" in ids
    assert "Datos de paciente guardados en el navegador" in ids


def test_paths_that_smell_like_health_data_are_signals() -> None:
    assert phi_signals(("src/fhir/patient.py", "src/util/fecha.py")) == ("src/fhir/patient.py",)
    assert phi_signals(("src/util/fecha.py",)) == ()


def test_typed_text_reports_types_never_values() -> None:
    tipos = scan_typed_text(f"El paciente nacido 1968-04-23, tel +34 611 22 33 44, ssn {SSN}")

    assert PhiIdentifier.SSN in tipos
    assert PhiIdentifier.FECHA in tipos
    assert PhiIdentifier.TELEFONO in tipos
    assert all(isinstance(t, PhiIdentifier) for t in tipos)


def test_typed_text_stays_quiet_on_an_ordinary_question() -> None:
    assert scan_typed_text("¿Por qué el agente de Kiuwan marcó ese defecto como falso positivo?") == ()


def test_classification_suggestion_never_decides_alone() -> None:
    valor, motivo = suggest_phi(title="Exportar movimientos", description="Listado con filtros")
    assert valor is PhiClassification.DESCONOCIDO  # sin señales: se aplica la política estricta
    assert motivo

    valor, motivo = suggest_phi(title="Resumen", description="Historia del paciente")
    assert valor is PhiClassification.SI
    assert "paciente" in motivo


class SpyProvider:
    """Proveedor que guarda literalmente lo que le llega y responde como el mock."""

    def __init__(self) -> None:
        self._real = MockLLMProvider()
        self.requests: list[ProviderRequest] = []
        self.tool_results: list[str] = []

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if request.run_tool is not None and request.tools:
            self.tool_results.append(await request.run_tool(request.tools[0].name, {}))
        return await self._real.complete(request)

    def sent(self) -> str:
        """Todo lo que ha salido hacia el proveedor, en un solo texto."""
        partes: list[str] = list(self.tool_results)
        for r in self.requests:
            partes += [r.system_prompt, r.task_prompt, str(r.context)]
        return "\n".join(partes)


def _request(run_id: str = "RUN-001", **context: Any) -> AgentRequest:
    return AgentRequest(
        run_id=run_id,
        agent_id=AgentId.CODE,
        profile=ProfileSnapshot(provider=ProviderId.MOCK, model="mock", prompt_version=1),
        system_prompt="Revisa el diff.",
        task_prompt=f"El paciente {NAME} aparece con ssn {SSN}.",
        context=context,
        phi=PhiClassification.SI,
    )


def test_nothing_reaches_the_provider_with_a_value() -> None:
    spy = SpyProvider()
    gateway = AIGateway(providers={ProviderId.MOCK: spy})

    run_async(gateway.run_agent(_request(codigo=CODIGO_CON_PHI)))

    enviado = spy.sent()
    for valor in VALORES:
        assert valor not in enviado, f"el proveedor recibió {valor}"
    assert "«PHI:ssn»" in enviado  # el modelo sí ve que ahí había algo


def test_the_gateway_counts_what_it_redacted() -> None:
    spy = SpyProvider()
    gateway = AIGateway(providers={ProviderId.MOCK: spy})

    result = run_async(gateway.run_agent(_request(codigo=CODIGO_CON_PHI)))

    assert result.redactions[PhiIdentifier.SSN] >= 1
    assert gateway.redactions("RUN-001")[PhiIdentifier.SSN] >= 1
    assert sum(gateway.redactions("RUN-001").values()) == sum(result.redactions.values())


def test_redaction_also_applies_without_phi_classification() -> None:
    """La clasificación es el juicio de una persona; el código puede llevar PHI igualmente."""
    spy = SpyProvider()
    gateway = AIGateway(providers={ProviderId.MOCK: spy})
    request = AgentRequest(
        run_id="RUN-002",
        agent_id=AgentId.CODE,
        profile=ProfileSnapshot(provider=ProviderId.MOCK, model="mock", prompt_version=1),
        system_prompt="Revisa el diff.",
        task_prompt="Sin datos sensibles declarados.",
        context={"codigo": CODIGO_CON_PHI},
        phi=PhiClassification.NO,
    )

    run_async(gateway.run_agent(request))

    assert SSN not in spy.sent()


def test_a_tool_result_is_redacted_before_going_back_to_the_model() -> None:
    """Un diff o un CSV vuelven al modelo: es la vía por la que más contenido sale."""

    class Registry:
        def specs_for(self, agent_id: AgentId) -> tuple[ToolSpec, ...]:
            return (ToolSpec(name="git_diff", description="diff", input_schema={"type": "object"}),)

        async def execute(
            self, agent_id: AgentId, tool: str, arguments: dict[str, Any], *, run_id: str = ""
        ) -> str:
            return CODIGO_CON_PHI

    spy = SpyProvider()
    gateway = AIGateway(providers={ProviderId.MOCK: spy}, tools=Registry())

    run_async(gateway.run_agent(_request()))

    assert spy.tool_results, "la herramienta no llegó a ejecutarse"
    for valor in VALORES:
        assert valor not in spy.tool_results[0]


def test_phi_blocks_a_provider_without_baa() -> None:
    motivo = check_agent_provider(AgentId.CODE, ProviderId.OPENROUTER, PhiClassification.SI)

    assert motivo is not None
    assert "BAA" in motivo
    assert "openrouter" in motivo


def test_an_unclassified_requirement_is_treated_as_phi() -> None:
    assert check_agent_provider(AgentId.CODE, ProviderId.OPENROUTER, PhiClassification.DESCONOCIDO)
    assert check_agent_provider(AgentId.CODE, ProviderId.OPENROUTER, PhiClassification.NO) is None


def test_the_gateway_refuses_to_call_a_provider_without_baa() -> None:
    spy = SpyProvider()
    gateway = AIGateway(providers={ProviderId.OPENROUTER: spy})
    request = AgentRequest(
        run_id="RUN-003",
        agent_id=AgentId.CODE,
        profile=ProfileSnapshot(provider=ProviderId.OPENROUTER, model="x", prompt_version=1),
        system_prompt="",
        task_prompt="",
        phi=PhiClassification.SI,
    )

    with pytest.raises(PolicyViolationError) as error:
        run_async(gateway.run_agent(request))

    assert "BAA" in str(error.value)
    assert spy.requests == []  # ni siquiera se intentó la llamada


def test_a_whole_run_leaves_no_value_anywhere(settings) -> None:
    spy = SpyProvider()
    gateway = AIGateway(providers={ProviderId.MOCK: spy})
    container = make_container(settings, gateway=gateway)

    requirement = run_async(
        container.create_requirement()(
            CreateRequirementCommand(
                title="Conciliación de la historia clínica",
                description=f"El paciente {NAME} (ssn {SSN}, mrn {MRN}) no aparece conciliado.",
                owner="ana",
                acceptance_criteria=(f"Buscar por member_id = {MEMBER}", f"Contacto: {EMAIL}"),
                phi=PhiClassification.SI,
                attachments=(
                    NewAttachment(kind=AttachmentKind.REPO, name="acme/clinica"),
                    NewAttachment(
                        kind=AttachmentKind.VTR_TEMPLATE,
                        name="VTR.docx",
                        detail=f"dob {DOB}",
                    ),
                ),
            )
        )
    )
    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement.id, started_by="ana", wait=True)
        )
    )
    assert run.status is RunStatus.COMPLETADA

    enviado = spy.sent()
    eventos = run_async(container.runs.events(run.id))
    traza = "\n".join(f"{e.title} {e.detail} {e.data}" for e in eventos)
    auditoria = "\n".join(
        f"{e.action} {e.target} {e.detail}" for e in run_async(container.audit.list(limit=500))
    )

    for valor in VALORES:
        assert valor not in enviado, f"el proveedor recibió {valor}"
        assert valor not in traza, f"la traza guardó {valor}"
        assert valor not in auditoria, f"la auditoría guardó {valor}"

    redactados = [e for e in eventos if e.type.value == "phi_redacted"]
    assert redactados, "la traza debería decir que se redactó algo"
    assert redactados[0].data["total"] >= 1
    assert "ssn" in redactados[0].data["counts"]
