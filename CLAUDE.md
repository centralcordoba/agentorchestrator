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
| VTR | **Genera** el documento Word VTR a partir de una plantilla modelo |
| Dictamen | Consolida hallazgos y emite APROBADO / CON OBSERVACIONES / RECHAZADO |

Flujo: Orquestador → Código → (Tests, Kiuwan, SQL, UI/UX en paralelo) → VTR → Dictamen.

Requisitos de producto: configurar el LLM de cada agente, ver qué hace cada agente al hacer clic en él, editar su prompt (con versiones) y un panel **Monitor** con los usuarios y agentes en uso. Uso previsto: **real** (código de la empresa enviado a LLMs; tenerlo en cuenta en decisiones de seguridad).

### Estado actual
- **Frontend nuevo = prototipo SIN backend** con datos simulados. Es lo que se está construyendo.
- **Backend (`backend/`) = sigue siendo la demo de bolsa.** Aún no se adaptó al nuevo dominio. Al construirlo, reutilizar su diseño: `Orchestrator.deliver()`, `EventBus` + WebSocket con replay, `RunStore`, bucle de herramientas del LLM, validación y guardarraíles, proveedores `mock` / `openrouter` / `anthropic`.
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
Backend (solo para `/demo-bolsa`): ver `README.md` §4 (`start-local.bat` o `uvicorn app.main:app --reload --port 8000` dentro de `backend/`, con `backend\.venv`). La configuración de proveedores está en `backend/.env` (contiene claves: no leer ni mostrar sus valores).

`frontend/out/` (export estático que sirve FastAPI) está versionado y **no** refleja el prototipo nuevo hasta ejecutar `npm run build:static`.

## Mapa del prototipo (frontend)
Rutas (`frontend/app/`), todas `"use client"` y compatibles con export estático (sin rutas dinámicas: el detalle usa `?id=` y `?tab=`):
- `/` lista y alta de requerimientos · `/requerimiento?id=REQ-…&tab=…` detalle por pestañas · `/agentes` configuración global · `/monitor` usuarios y agentes · `/demo-bolsa` demo antigua.

Lógica en `frontend/lib/rq/`:
| Archivo | Responsabilidad |
|---|---|
| `types.ts` | Modelo de dominio (Requirement, Attachment, RepoInfo, Plan, Run, TraceEvent, entregables) |
| `agents.ts` | Catálogo de agentes, catálogo de modelos con precios (IDs de OpenRouter reales), perfiles y prompts por defecto |
| `store.tsx` | Contexto React + persistencia en `localStorage` (`rq-prototipo-v1`); perfiles globales y ajustes por requerimiento; `useNow()` |
| `planner.ts` | Sugerencia de plan y avisos (adjunto faltante = bloqueo; dependencia desactivada = aviso) |
| `simulator.ts` | Traza **determinista** derivada de `run.startedAt` + desfases: los eventos no se guardan, se recalculan (sobrevive a recargas) |
| `scenarios.ts` | Entregables de ejemplo (escenarios `pagos` y `portal`), mezcla con datos reales del repo y cálculo del dictamen |
| `github.ts` | Conexión real con repos **públicos** de GitHub y análisis del diff por reglas |
| `derive.ts` / `monitor.ts` | Estado derivado de ejecuciones · datos del Monitor (otros usuarios simulados, estables por ventanas de 20 s) |

Componentes en `frontend/components/rq/` (`FlowGraph`, `AgentPanel`, `ProfileEditor`, `RepoConnector`, `EventRow`, `ui.tsx` y `tabs/`).

## Reglas importantes del prototipo
- **No presentar datos inventados como reales.** Con un repositorio conectado, solo **Código y SQL** usan datos reales (diff de GitHub + reglas deterministas, sin LLM). Tests, Kiuwan, UI/UX y el resto del VTR son de ejemplo y se marcan con `SourceNote`. El dictamen de un repo real solo considera Código y SQL (regla G0). Mantener esta separación al añadir funciones.
- Los hallazgos reales deben apuntar a archivo y línea existentes (`Finding.url` enlaza a GitHub en el `headSha`).
- API de GitHub sin token: **60 peticiones/hora por IP**; conectar un repo consume ~5. No añadir llamadas en bucle ni por render. No pedir ni guardar tokens en `localStorage`.
- El esquema de salida y las herramientas de cada agente **no son editables** desde la UI (el consolidador y los guardarraíles dependen de ellos); sí lo son el prompt de sistema, la plantilla de tarea, el modelo y los parámetros.
- Cada ejecución congela el proveedor, el modelo y la versión del prompt de cada agente (`Run.profiles`).
- `reactStrictMode` está activo: los efectos de carga y guardado se ejecutan dos veces en dev (por eso la persistencia espera a `ready`).
- Hashes o índices a partir de enteros sin signo: usar `>>>`, no `>>` (un índice negativo rompió el Monitor).

## Estilo visual
Paleta cálida definida en `frontend/tailwind.config.ts` (`paper`, `surface`, `sunken`, `ink-*`, acento terracota `accent`, semánticos `ok/warn/danger/info`) y clases `panel`, `panel-title`, `chip`, `pill`, `btn-primary`, `btn-ghost` en `app/globals.css`. Reutilizarlas en vez de colores sueltos. Severidades y estados siempre con icono o texto, no solo color.

## Verificación
- `cd frontend && npx tsc --noEmit` (ESLint no está configurado; `next lint` abre un asistente interactivo).
- `npx next build` compila todas las rutas (no ejecutarlo con `next dev` corriendo: comparten `.next`).
- Pruebas en navegador: `@playwright/test` está instalado **globalmente** (`npm root -g`), pero su navegador por defecto no está descargado; lanzar con `executablePath` apuntando a `%LOCALAPPDATA%\ms-playwright\chromium-1208\chrome-win*\chrome.exe`. Guardar scripts y capturas fuera del repositorio.

## Entorno
Windows 11. Bash (Git Bash) y PowerShell disponibles; en CMD usar `copy` en vez de `cp` y `.venv\Scripts\activate.bat`.
