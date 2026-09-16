# CLAUDE.md

## Idioma
- Textos de interfaz, documentación y comentarios en **español**. Identificadores de código en **inglés**.

## Git
- **Nunca hacer `git commit`** (ni `git push`, `git commit --amend`, rebase u otras operaciones que creen o reescriban commits). Los commits los hace el usuario a mano.
- Dejar los cambios en el árbol de trabajo y, al terminar, indicar qué archivos cambiaron para que el usuario decida qué incluir.

## Qué es este proyecto (y en qué punto está)
El repositorio empezó como una **demo educativa de agentes que analizan acciones de bolsa** (backend FastAPI + frontend Next.js, ver `README.md` y `docs/COMO_FUNCIONA.md`).

Ahora el enfoque cambió: **un orquestador multiagente que revisa el proceso de desarrollo de un requerimiento**. Todo gira alrededor de un **Requerimiento**, del que cuelgan los adjuntos, el plan de agentes, las ejecuciones y los entregables.

| Agente | Rol |
|---|---|
| Orquestador | Lee el requerimiento y los adjuntos, **sugiere** qué agentes usar (el usuario los activa o desactiva a mano) y coordina |
| Código | Revisa el diff del repositorio git y produce el "mapa del cambio" que consumen los demás |
| Tests | Genera pruebas pequeñas con todo el contexto y las ejecuta en local |
| Kiuwan | Analiza el CSV de Kiuwan adjunto |
| SQL | Revisa scripts y consultas (condicional) |
| UI/UX | Pruebas con Playwright (condicional) |
| Privacidad HIPAA | Detecta PHI en el cambio y evalúa las salvaguardas 45 CFR 164.312 (obligatorio si el requerimiento maneja PHI) |
| VTR | **Genera** el documento Word VTR a partir de una plantilla modelo |
| Dictamen | Consolida hallazgos y emite APROBADO / CON OBSERVACIONES / RECHAZADO |
| Asistente de consulta (`chat`) | Responde preguntas sobre una revisión ya ejecutada citando la evidencia. Fuera del flujo: `AGENT_ORDER` no lo incluye, `ALL_AGENTS` sí |

Flujo: Orquestador → Código → (Tests, Kiuwan, SQL, UI/UX y Privacidad en paralelo) → VTR → Dictamen.

Requisitos de producto: configurar el LLM de cada agente, ver qué hace cada agente al hacer clic en él, editar su prompt (con versiones) y un panel **Monitor** con los usuarios y agentes en uso. Uso previsto: **real, en una empresa de salud sujeta a HIPAA** (código de la empresa enviado a LLMs; tenerlo en cuenta en decisiones de seguridad). De ahí el agente de Privacidad, el gobierno de IA (`/gobierno`) y el panel de cumplimiento del Monitor.

### Estado actual
- **Frontend: mitad migrado.** Requerimientos (lista y detalle), plan, ejecución en vivo y entregables consumen el backend real. Gobierno, Monitor y la configuración de agentes siguen con datos de ejemplo (`mockData.ts`, `scenarios.ts`, `simulator.ts`, `monitor.ts`) hasta que ORQ-21, ORQ-5 y ORQ-29 den lo que necesitan.
- **Backend nuevo = `backend/orq/`**: dominio del requerimiento por capas (`domain` / `application` / `infrastructure` / `api`), registro de los 10 agentes con esquema y herramientas de solo lectura, motor de orquestación por grafo de dependencias con traza y perfiles congelados, capa de IA única (proveedores `mock` / `anthropic` / `openrouter`) y persistencia en PostgreSQL con Alembic, cifrado en reposo y auditoría encadenada. Sin `DATABASE_URL` arranca en memoria. Detalles y pendientes en `backend/orq/README.md`. Se arranca con `uvicorn orq.main:app --port 8001` y se prueba con `pytest` dentro de `backend/`.
- **`backend/app/` = demo de bolsa**, intacta y aislada hasta que se retire (ORQ-32). De ella se reutiliza el diseño: `Orchestrator.deliver()`, `EventBus` + WebSocket con replay, `RunStore`, bucle de herramientas del LLM, validación y guardarraíles, proveedores `mock` / `openrouter` / `anthropic`.
- La demo de bolsa del frontend se conserva en la ruta `/demo-bolsa` (necesita el backend).

### Pendiente / decisiones del usuario
- Código: repositorio git con rama. Tests: locales. UI/UX: Playwright.
- La plantilla VTR estará en `doc/vtr` y un CSV de ejemplo de Kiuwan en `doc/kiwuan`. **Todavía no existen**: cuando aparezcan, ajustar las secciones del VTR y las columnas del CSV (hoy son inventadas en `scenarios.ts`).

## Cómo ejecutar
Frontend (prototipo, sin backend), desde CMD o PowerShell:
```
cd frontend
npm install
npm run dev        # http://localhost:3000
```
Backend nuevo (orquestador), dentro de `backend/` y con `backend\.venv`:
```
uvicorn orq.main:app --reload --port 8001    # http://localhost:8001/api/health · /docs
```
Con `AI_PROVIDER=mock` (valor por defecto) el flujo completo funciona sin claves ni red, y sin
`DATABASE_URL` guarda en memoria. Para persistencia real: contenedor de PostgreSQL,
`DATABASE_URL`, `DB_ENCRYPTION_KEY` (obligatoria: las columnas con contenido van cifradas) y
`alembic upgrade head`. Todo documentado en `backend/.env.example` y `backend/orq/README.md`.

Backend de la demo de bolsa (solo para `/demo-bolsa`): ver `README.md` §4 (`start-local.bat` o `uvicorn app.main:app --reload --port 8000`). La configuración de proveedores está en `backend/.env` (contiene claves: no leer ni mostrar sus valores).

`frontend/out/` (export estático que sirve FastAPI) está versionado y **no** refleja el prototipo nuevo hasta ejecutar `npm run build:static`.

## Mapa del prototipo (frontend)
Rutas (`frontend/app/`), todas `"use client"` y compatibles con export estático (sin rutas dinámicas: el detalle usa `?id=` y `?tab=`):
- Sin sesión, `AppShell` enseña `LoginScreen` y no se pinta nada más.
- `/` lista y alta de requerimientos **(API)** · `/requerimiento?id=REQ-…&tab=…` detalle por pestañas **(API)** ·
  `/ejecucion?run=RUN-…` ejecución en vivo por WebSocket **(API)** · `/agentes` configuración global ·
  `/gobierno` control de cambios, fichas y auditoría · `/monitor` actividad y cumplimiento HIPAA · `/demo-bolsa` demo antigua.
- Las pantallas marcadas **(API)** no leen `localStorage`: los datos vienen de `lib/api/`. Las demás
  siguen sobre el store simulado.

Lógica en `frontend/lib/rq/`:
| Archivo | Responsabilidad |
|---|---|
| `types.ts` | Modelo de dominio (Requirement, Attachment, RepoInfo, Plan, Run, TraceEvent, entregables) |
| `agents.ts` | Catálogo de agentes, catálogo de modelos con precios (IDs de OpenRouter reales), perfiles y prompts por defecto |
| `store.tsx` | Contexto React + persistencia en `localStorage` (`rq-prototipo-v4`); perfiles globales, ajustes por requerimiento, solicitudes de cambio, firmas, auditoría y chats; `useNow()` |
| `planner.ts` | Sugerencia de plan y avisos (adjunto faltante = bloqueo; dependencia desactivada = aviso) |
| `simulator.ts` | Traza **determinista** derivada de `run.startedAt` + desfases: los eventos no se guardan, se recalculan (sobrevive a recargas) |
| `scenarios.ts` | Entregables de ejemplo (escenarios `pagos` y `portal`), mezcla con datos reales del repo y cálculo del dictamen |
| `repo.ts` | Ayudas de formato sobre un repositorio ya conectado. **Sin red**: clonar y calcular el diff es del servidor (ORQ-22) |
| `privacy.ts` | Agente de Privacidad HIPAA: reglas de detección de PHI, salvaguardas 164.312 y sugerencia de clasificación |
| `governance.ts` | Roles y permisos, control de cambios (cuatro ojos), evaluación de regresión, fichas de agente y auditoría encadenada |
| `compliance.ts` | Indicadores y alertas del panel de cumplimiento |
| `chat.ts` | Asistente de consulta: preguntas sugeridas y respuestas por reglas sobre los datos de la ejecución, con citas |
| `derive.ts` / `monitor.ts` | Estado derivado de ejecuciones · datos del Monitor (otros usuarios simulados, estables por ventanas de 20 s) |

Componentes en `frontend/components/rq/`:
- Sobre la API: `detail/` (requerimiento, plan y entregables), `LiveRun.tsx` (traza en vivo),
  `FlowGraph.tsx` (grafo del flujo: columnas derivadas del mismo grafo de dependencias que usa el
  motor) y `AsyncState.tsx` (cargando / vacío / error).
- Sobre datos de ejemplo, hasta que se migre su sección: `governance/`, `monitor/`, `ProfileEditor`,
  `SignoffPanel`.
- Comunes: `ui.tsx`, `AppShell.tsx`, `PhiControl.tsx`.

## Reglas importantes del prototipo
- **No presentar datos inventados como reales.** Con un repositorio conectado, el mapa del cambio y los hallazgos de **Código y SQL** salen del diff real y de reglas deterministas en el servidor (`domain/diff.py` y `domain/code_review.py`), sin LLM. Además, un hallazgo del modelo que señale un archivo que no está en el cambio **se descarta** y queda dicho en la traza: no puede llegar al dictamen algo que no se puede comprobar contra el commit. Tests, Kiuwan, UI/UX y el resto del VTR siguen siendo de ejemplo y se marcan como tales. Mantener esta separación al añadir funciones.
- Los hallazgos reales deben apuntar a archivo y línea existentes (`Finding.url` enlaza a GitHub en el `headSha`).
- **El navegador no habla con ningún proveedor de git.** Conectar un repositorio es `POST /api/requirements/{id}/repo`: el servidor clona, resuelve la rama y calcula el diff (ORQ-22). No pedir ni guardar tokens en el cliente.
- **Identidad (ORQ-5): el actor sale de la sesión, nunca del cliente.** Ninguna ruta de datos responde sin sesión; `api/deps.py` da `current_user` y `requires(Permission…)`, y cada endpoint **declara** el permiso que necesita. La UI solo oculta lo que además está bloqueado en el servidor. Al añadir un endpoint, ponerle su dependencia: hay una prueba que recorre el contrato y falla si alguno responde sin sesión. `User` no tiene contraseña; el hash solo lo tocan `application/auth.py` y el repositorio, y otra prueba lo vigila.
- **Secretos: se escriben, se usan y no se leen.** Viven cifrados en la bóveda (ORQ-18, `orq/domain/secrets.py` y `orq/infrastructure/secrets/`). `SecretMetadata` —lo que sale hacia la API— no tiene campo para el valor, y no existe ningún endpoint que lo devuelva. Al añadir un secreto nuevo: guardarlo con `SaveSecret`, leerlo solo con `vault.reveal()` desde el backend y dejar que el tachador (`SecretScrubber`, enganchado al logger raíz) lo oculte en logs y trazas.
- El esquema de salida y las herramientas de cada agente **no son editables** desde la UI (el consolidador y los guardarraíles dependen de ellos); sí lo son el prompt de sistema, la plantilla de tarea, el modelo y los parámetros.
- Cada ejecución congela el proveedor, el modelo y la versión del prompt de cada agente (`Run.profiles`).
- `reactStrictMode` está activo: los efectos de carga y guardado se ejecutan dos veces en dev (por eso la persistencia espera a `ready`).
- Hashes o índices a partir de enteros sin signo: usar `>>>`, no `>>` (un índice negativo rompió el Monitor).
- **PHI:** nunca mostrar, guardar ni enviar el valor de un identificador detectado; solo tipo, archivo y línea. Con
  `phi !== "no"` el agente de Privacidad es obligatorio y el dictamen no puede ser `APROBADO` sin él.
  En el backend el guardarraíl está en `orq/domain/privacy.py` y lo aplica la pasarela de IA a todo
  lo que sale hacia un proveedor (prompt, contexto y resultado de herramientas), siempre, sin mirar
  la clasificación. Al añadir un camino nuevo hacia un LLM, que pase por la pasarela: es lo que
  garantiza la redacción.
- **Control de cambios:** editar la configuración **predeterminada** de un agente crea una solicitud (`ChangeRequest`), no aplica
  el cambio. Aprobar exige permiso, cuatro ojos, evaluación ejecutada y ningún bloqueo de BAA. Los ajustes por requerimiento sí se
  aplican al momento, pero quedan en la auditoría.
- **Auditoría:** toda acción relevante pasa por `appendAudit` y encadena el hash anterior; no reescribir entradas existentes.
- La clave de `localStorage` sube de versión cuando cambia la forma de los datos (hoy `rq-prototipo-v4`).
- **Asistente:** solo lee. Cada respuesta cita la evidencia y, si el dato no está en la ejecución, lo dice (`fallback`). No puede
  firmar ni aprobar. El texto que escribe el usuario pasa por `scanTypedText` antes de enviarse, y en la auditoría se guardan
  metadatos, nunca la pregunta.
- **Cuidado al escribir expresiones regulares desde scripts de shell:** un `\b` mal escapado dejó un carácter de control dentro de
  una regex de `privacy.ts` y la volvió inservible. Escribir esos archivos con la herramienta de edición, no por heredoc.

## Estilo visual
Paleta cálida definida en `frontend/tailwind.config.ts` (`paper`, `surface`, `sunken`, `ink-*`, acento terracota `accent`, semánticos `ok/warn/danger/info`) y clases `panel`, `panel-title`, `chip`, `pill`, `btn-primary`, `btn-ghost` en `app/globals.css`. Reutilizarlas en vez de colores sueltos. Severidades y estados siempre con icono o texto, no solo color.

## Contrato de la API
El backend publica su contrato en `backend/openapi.json` (versionado). De ahí salen los tipos del
frontend: `frontend/lib/api/schema.d.ts`, generados con `npm run api:types` y comprobados por
`npm run api:check`, que forma parte de `npm run typecheck`. Al cambiar una respuesta del backend:
1. `cd backend && .venv\Scripts\python.exe scripts/export_openapi.py`
2. `cd frontend && npm run api:types`
Si se olvida, fallan `tests/test_contract.py` (backend) y `npm run typecheck` (frontend).

El cliente del frontend está en `frontend/lib/api/`: `client.ts` (peticiones y errores),
`useResource.ts` (caché con revalidación) y `types.ts` (alias de los tipos generados). Los estados
de carga, vacío y error se pintan con `components/rq/AsyncState.tsx`.

## Verificación
- Backend: `cd backend && .venv\Scripts\python.exe -m pytest` (incluye una prueba de arquitectura que falla si el dominio importa un framework o si los casos de uso importan infraestructura). Las pruebas contra PostgreSQL se saltan salvo que se defina `TEST_DATABASE_URL`. **Esa variable debe apuntar a una base aparte** (`orq_test`): las pruebas vacían las tablas, así que apuntarla a la base de la demo borra sus datos.
- `cd frontend && npm run typecheck` (comprueba el contrato de la API y luego `tsc --noEmit`; ESLint no está configurado).
- `npx next build` compila todas las rutas (no ejecutarlo con `next dev` corriendo: comparten `.next`).
- Pruebas en navegador: `@playwright/test` está instalado **globalmente** (`npm root -g`), pero su navegador por defecto no está descargado; lanzar con `executablePath` apuntando a `%LOCALAPPDATA%\ms-playwright\chromium-1208\chrome-win*\chrome.exe`. Guardar scripts y capturas fuera del repositorio.

## Entorno
Windows 11. Bash (Git Bash) y PowerShell disponibles; en CMD usar `copy` en vez de `cp` y `.venv\Scripts\activate.bat`.
