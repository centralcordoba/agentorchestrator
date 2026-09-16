# Backend del orquestador

Servicio del dominio nuevo: **un requerimiento**, del que cuelgan adjuntos, plan de agentes,
ejecuciones y entregables. Convive con `backend/app/`, que sigue siendo la demo de bolsa hasta
que se retire (ORQ-32).

## Arrancar en local

```
cd backend
.venv\Scripts\activate.bat          # CMD; en Git Bash: source .venv/Scripts/activate
pip install -e ".[dev]"             # o: pip install -r requirements.txt && pip install pytest
uvicorn orq.main:app --reload --port 8001
```

- API: `http://localhost:8001/api/health`
- Documentación interactiva: `http://localhost:8001/docs`
- La demo de bolsa sigue en `uvicorn app.main:app --port 8000`.

Con `AI_PROVIDER=mock` (valor por defecto) el flujo completo funciona **sin claves ni red**.
Otros valores: `anthropic`, `openrouter` (fuerzan ese proveedor en todos los agentes) y `perfil`
(cada agente usa el proveedor de su perfil). Sin la clave correspondiente, el proveedor falla con
un mensaje explícito en vez de simular una respuesta.

Variables útiles: `AI_TIMEOUT_S`, `AI_RETRY_ATTEMPTS`, `AI_MAX_ATTEMPTS`, `AI_MAX_OUTPUT_TOKENS`,
`RUN_MAX_TOKENS` y `RUN_MAX_COST_USD` (techo por ejecución; `0` = sin límite). Todas están
documentadas en `backend/.env.example`.

## Base de datos

Sin `DATABASE_URL` el servicio arranca con persistencia **en memoria**: sirve para probar la app,
pero se pierde todo al reiniciar. Para la persistencia real:

```
docker run -d --name orq-postgres -e POSTGRES_PASSWORD=orq -e POSTGRES_USER=orq ^
    -e POSTGRES_DB=orq -p 55432:5432 postgres:16-alpine

set DATABASE_URL=postgresql://orq:orq@localhost:55432/orq
set DB_ENCRYPTION_KEY=...    # python -c "from orq.infrastructure.db import Cipher; print(Cipher.generate_key())"
alembic upgrade head
uvicorn orq.main:app --reload --port 8001
```

`DB_ENCRYPTION_KEY` es **obligatoria** cuando hay base de datos: sin ella el servicio no arranca,
porque las columnas con contenido del cliente se guardan cifradas (Fernet) y la clave vive fuera
de la base. Si se pierde, el contenido guardado no se puede recuperar.

Las pruebas de integración usan `TEST_DATABASE_URL`; sin esa variable se saltan. Apúntala siempre a
una base aparte (`orq_test`): vacían las tablas antes de cada prueba, así que sobre la base de
trabajo borran lo que haya.

## Pruebas

```
cd backend
.venv\Scripts\python.exe -m pytest
```

Ninguna prueba usa la red ni llama a un LLM real.

## Capas

| Carpeta | Qué contiene | De quién depende |
|---|---|---|
| `domain/` | Entidades, registro de agentes, reglas de plan y políticas de cumplimiento | Solo biblioteca estándar |
| `application/` | Casos de uso, puertos y ejecutor de la revisión | `domain` y sus puertos |
| `infrastructure/` | Persistencia, bus de eventos, capa de IA y proveedores | `domain` y `application` |
| `api/` | Routers FastAPI, contenedor de dependencias y serialización | Todo lo anterior |

`tests/test_architecture.py` falla si alguna de esas flechas se invierte.

## Lo que ya está y lo que no

Está: modelo de dominio completo, registro de los 10 agentes con su esquema y sus herramientas,
sugerencia de plan con las reglas del prototipo, motor de orquestación y API HTTP.

El motor (ORQ-15) deriva el orden del grafo de dependencias, no de una lista escrita a mano:
Orquestador → Código → (Tests, Kiuwan, SQL, UI/UX y Privacidad en paralelo) → VTR → Dictamen.
La revisión corre en segundo plano —`POST /runs` responde de inmediato con la ejecución en
curso—, se puede cancelar (`POST /runs/{id}/cancel`) y, si el servicio se cae, al arrancar se
reanuda lo pendiente sin repetir lo hecho y con los perfiles congelados, no los de hoy.
El plan se puede pedir asistido por el Orquestador (`POST /requirements/{id}/plan?assisted=true`):
sugiere, pero no puede saltarse lo obligatorio.

La persistencia (ORQ-13) es PostgreSQL con migraciones Alembic, repositorios por agregado,
cifrado en reposo de todo lo que puede contener contenido del cliente, retención con purga en
cascada, contador de identificadores en la base y auditoría encadenada de solo anexado.

El canal en vivo (ORQ-17) es un WebSocket por ejecución: `ws://…/api/runs/{id}/stream?afterSeq=N`.
Manda `hello` con el estado, luego el **replay** de lo ya ocurrido, luego los eventos nuevos, un
`ping` cada 20 s y un `end` al terminar. La suscripción al bus se abre antes de leer lo guardado,
así que no quedan huecos; el cliente que se reconecta manda `afterSeq` y no recibe repetidos.

La API (ORQ-16) tiene modelos de respuesta tipados, una forma única de error (`code`, `message`,
`detail`), paginación en las listas que crecen y un contrato versionado en `backend/openapi.json`
del que el frontend genera sus tipos. `scripts/export_openapi.py` lo exporta y
`tests/test_contract.py` falla si el archivo se queda atrás.

La capa de IA (ORQ-14) incluye: proveedores `mock`, `anthropic` (SDK oficial, salida
estructurada y pensamiento adaptativo) y `openrouter` (HTTP, `response_format` con esquema),
bucle de herramientas con registro de implementaciones, validación de esquema con reintento,
reintentos con espera progresiva y tiempo máximo, presupuesto por ejecución, cálculo de coste y
registro de cada llamada (metadatos, nunca contenido).

No está todavía, con tarea propia:

| Falta | Tarea |
|---|---|
| Herramientas reales (`run_tests`, `parse_kiuwan_csv`, `playwright_run`…) | ORQ-23 a ORQ-26 |

### Identidad y permisos (ORQ-5)

Sin sesión válida **ninguna ruta de datos responde**. La sesión va en una cookie `HttpOnly`,
`SameSite=Lax` y `Secure` cuando el despliegue tiene TLS; el testigo no se guarda en la base,
solo su SHA-256.

- **El actor sale de la sesión**, nunca del cuerpo de la petición: antes la API aceptaba un
  `by` del cliente, y eso convierte la auditoría en una declaración de intenciones.
- **Los permisos se comprueban en el servidor.** Cada endpoint declara el suyo con
  `Depends(requires(Permission.…))`; la UI solo oculta lo que además está bloqueado aquí.
- **La sesión caduca por dos motivos**: tope absoluto e inactividad (HIPAA 164.312(a)(2)(iii)).
  Cuando caduca, el 401 lleva `X-Sesion-Caducada` para que la UI diga por qué.
- **Contraseñas con scrypt** (RFC 7914, biblioteca estándar), sal por contraseña y comparación
  en tiempo constante. El formato guardado lleva el algoritmo por delante, así que cambiar a
  argon2 es añadir un verificador, no migrar a ciegas.
- Cambiar el rol o desactivar una cuenta **cierra sus sesiones abiertas** en el acto.
- `User.provider` (`local` / `oidc`) deja la puerta abierta al inicio de sesión corporativo:
  una cuenta de OIDC simplemente no tiene credencial local.

La cuenta inicial se siembra al arrancar con `ADMIN_EMAIL` y `ADMIN_PASSWORD`, **solo si no
hay ninguna**, y nace marcada para cambiar la contraseña.

### Bóveda de secretos (ORQ-18)

Credenciales de terceros —token de repositorio privado, usuario del sitio del agente UI/UX,
claves de proveedores— cifradas en reposo con la misma `Cipher` que el resto del contenido.

- **Se escribe y no se lee.** `SecretMetadata`, lo único que sale hacia arriba, no tiene campo
  donde quepa el valor, así que ningún endpoint puede devolverlo por descuido. `reveal()` es el
  único camino al valor y lo llama el backend cuando va a usarlo; una prueba de arquitectura
  comprueba que ningún router lo llama.
- **Rotar es volver a guardar** el mismo tipo, nombre y ámbito: sustituye el valor y levanta una
  revocación anterior. **Revocar borra el valor de la base**, no solo marca la fila.
- **Ámbito**: un secreto de un requerimiento manda sobre el de la organización, así que una
  revisión puede usar el token de otro cliente sin tocar el general.
- **Tachado**: `SecretScrubber` conoce los valores vivos y los sustituye por `«secreto»` en la
  traza, en lo que sale hacia un proveedor y en **todo** el logging, incluido el de bibliotecas
  de terceros: el filtro se instala en el logger raíz al arrancar.
- Cada uso queda en la auditoría con el host, el agente y la ejecución. Nunca el valor.

### Guardarraíl de PHI (ORQ-20)

Las reglas viven en `domain/privacy.py` (dominio puro: solo `re`). La pasarela las aplica justo
antes de llamar al proveedor, de modo que **cualquier camino nuevo hacia un LLM queda cubierto**
sin acordarse de nada:

- `redact()` sustituye el valor por un marcador con el tipo (`«PHI:ssn»`): el modelo sigue viendo
  la forma del código y puede señalar el problema, pero no recibe el dato.
- Se redactan el prompt de sistema, la plantilla de tarea, el contexto completo (recursivo: listas
  y diccionarios anidados) y **lo que devuelve cada herramienta**, que es por donde más contenido
  del cliente sale.
- Se aplica **siempre**, no solo con `phi = "si"`: la clasificación es el juicio de una persona
  sobre lo que el requerimiento debería tocar, y el código puede llevar PHI igualmente.
- `Detection` no tiene ningún campo donde quepa el valor, así que no puede filtrarse a la traza,
  a la auditoría ni a un log por descuido. La métrica por ejecución son recuentos por tipo:
  `gateway.redactions(run_id)` y un evento `phi_redacted` por agente.
- `analyze_source()` y `scan_typed_text()` portan el análisis determinista y la pasarela DLP del
  texto que escribe una persona; `suggest_phi()`, la sugerencia de clasificación.

## Reglas que el código ya hace cumplir

- El **esquema de salida** y las **herramientas** de un agente no son editables: viven en
  `domain/agents.py` como estructuras de solo lectura.
- Un agente que procesaría PHI con un proveedor **sin BAA** no se ejecuta.
- Un agente solo puede usar las herramientas que declara; cualquier otra se rechaza y queda
  registrada como intento rechazado.
- Una ejecución tiene techo de tokens y de dinero; superarlo la corta.
- Con PHI y sin informe de Privacidad, el dictamen **no puede ser `APROBADO`**.
- Una ejecución **congela** proveedor, modelo y versión de prompt de cada agente.
- Un agente que falla no tumba la ejecución: se registra y el dictamen lo refleja.
- Lo que no se ejecutó **no se rellena con datos de ejemplo**: se declara en `missing`.
- Cancelar corta las llamadas en curso y ningún agente se queda en `trabajando`.
- Reanudar usa el prompt de la versión congelada; si ya no está, la ejecución se marca como
  fallida en vez de continuar con otra configuración.
- Los perfiles congelados de una ejecución no se reescriben: el `UPDATE` de la tabla `runs` los
  excluye a propósito.
- La auditoría es de solo anexado y encadenada por hash: no hay operación de modificar ni borrar,
  y alterar una fila rompe la verificación de `GET /api/audit/verify`.
- El contenido del cliente va cifrado en reposo; quien lea la base sin la clave no ve nada.
