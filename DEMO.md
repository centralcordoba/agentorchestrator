# Demo del orquestador

Guion para enseñar el estado actual a otros desarrolladores. **El flujo funciona de verdad**: no
hay pantallas de mentira ni clics preparados. Lo que todavía no es real es el *análisis* de los
agentes, y eso conviene decirlo al principio para que nadie se lleve una impresión equivocada.

---

## 1. Arrancar (un comando)

```
demo.bat
```

Levanta PostgreSQL en Docker (si está disponible), el backend en el 8001, el frontend en el 3000
y siembra tres requerimientos de ejemplo. Deja dos ventanas abiertas: cerrarlas apaga la demo.

Para empezar de cero:

```
demo.bat limpio
```

Abre **http://localhost:3000**. La aplicación pide entrar: **demo@orquestador.local** /
**demo-orquestador-2026** (la crea `demo.bat` la primera vez). El contrato de la API, por si
alguien lo pide, está en **http://localhost:8001/docs**.

> Si Docker no está levantado, la demo funciona igual con persistencia en memoria; lo único que
> se pierde es poder reiniciar el backend y que los datos sigan ahí.

> La clave que cifra el contenido se crea la primera vez en `%LOCALAPPDATA%\orq-demo\clave.txt`,
> **fuera del repositorio**, y se reutiliza en los arranques siguientes. Si se borra, lo guardado
> antes en PostgreSQL ya no se puede descifrar: hay que lanzar `demo.bat limpio`. En uso real la
> clave viene de un gestor de secretos (ORQ-18), no de un archivo.

---

## 2. Lo que se enseña, en orden

### a) Entrar — *«sin saber quién eres no hay auditoría»*

La primera pantalla es el login, y merece treinta segundos: cada acción queda registrada con
el nombre de quien la hizo, y de eso dependen la auditoría, las firmas y el cuatro ojos del
control de cambios. Antes el usuario se elegía en un desplegable; ahora hay sesión de verdad
en una cookie que el JavaScript de la página no puede leer.

Si quieres enseñarlo: **prueba con la contraseña mal**. El mensaje es el mismo exista o no el
correo —decir «ese usuario no existe» le confirma a quien prueba direcciones cuáles valen— y
a los cinco intentos la cuenta se bloquea.

### b) Lista de requerimientos — *«todo cuelga de un requerimiento»*

Tres filas sembradas, cada una en un estado distinto: dos ejecutadas y una bloqueada. Se ve la
clasificación de PHI, qué adjuntos tiene cada una, qué agentes se planificaron y el dictamen.

Los datos vienen de `GET /api/requirements`. Si alguien duda, abre la pestaña de red del
navegador: no hay `localStorage`.

### c) Alta de un requerimiento — *«el orquestador no adivina, pregunta»*

«Nuevo requerimiento» y rellena algo corto. Lo importante: **la clasificación de PHI es
obligatoria** para poder crear. No es un adorno: decide qué agentes son obligatorios después.

### d) Adjuntos y clasificación — pestaña **Requerimiento**

Añade el repositorio y la plantilla VTR. Di en voz alta lo que aún no hace: hoy guarda el tipo y
el nombre; la subida del archivo con cifrado y retención es una tarea aparte (ORQ-19).

### e) Plan — pestaña **Plan** *(aquí está media demo)*

«Pedir plan». Cada agente sale con **su motivo**, y ese motivo se lee:

- *«El requerimiento menciona "tabla": probablemente hay consultas»* → reglas deterministas sobre
  el texto y los adjuntos, no un modelo adivinando.
- *Privacidad HIPAA* aparece **bloqueado** cuando hay PHI: no se puede desactivar ni forzando la
  petición contra la API.
- Desactiva un agente del que otro depende: sale un **aviso**, no un bloqueo. La diferencia
  importa.

Enseña también **REQ-003**: su plan está **bloqueado** porque falta la plantilla VTR. El botón de
ejecutar está deshabilitado y dice por qué.

Si quieres enseñar el plan asistido: «Proponer con el Orquestador» pasa la propuesta por el
modelo, que puede cambiar sugerencias y motivos pero **no** puede desactivar lo obligatorio.

### f) Ejecutar — pestaña **Ejecución** *(el momento visual)*

Pulsa «Ejecutar revisión». La pantalla salta a Ejecución y se ve:

- El chip **● En vivo**: es un WebSocket, no un refresco cada X segundos.
- Los agentes cambiando de estado según terminan.
- La traza creciendo evento a evento, con tokens y coste por llamada.

Cuentalo así: **Orquestador → Código → (Tests, Kiuwan, SQL, UI/UX y Privacidad en paralelo) → VTR
→ Dictamen**. El orden no está escrito a mano: sale del grafo de dependencias de cada agente.

Dos cosas que puedes provocar en directo:

- **Recargar la página a media ejecución**: la traza aparece entera desde el principio y sigue en
  vivo. Es el *replay* del canal.
- **Cancelar**: corta las llamadas en curso y ningún agente se queda colgado en «trabajando».

### g) Entregables — las ocho pestañas

Código, Tests, Kiuwan, SQL, UI/UX, Privacidad, VTR y Dictamen. Con la configuración de la demo
(`AI_MOCK_RICH=1`) los informes traen **contenido de ejemplo coherente entre agentes**, para que
se entienda qué produce cada uno:

- **Código**: 5 archivos en el mapa del cambio y tres hallazgos, uno alto.
- **Tests**: tres pruebas con su resultado y la cobertura.
- **Kiuwan**: tres defectos, uno marcado como falso positivo *confirmado con el agente de Código*
  — buen momento para contar que los agentes se hablan entre ellos.
- **Privacidad**: un identificador de paciente detectado **en un log** y las cinco salvaguardas de
  164.312 evaluadas. Fíjate: se dice el tipo, el archivo y la línea, **nunca el valor**.
- **VTR**: las seis secciones del documento, algunas marcadas como *parciales*.
- **Dictamen**: en REQ-001 sale **Rechazado**, y no es una casualidad preparada: el hallazgo
  crítico de Privacidad dispara el umbral del dominio. REQ-002, sin PHI, sale *aprobado con
  observaciones*.

**Lo que hay que decir en voz alta**: arriba de esas pestañas hay un aviso naranja —*«Ejecución
con el proveedor simulado: los informes son de ejemplo, no un análisis del código»*—. Está puesto
a propósito. La regla del proyecto es **no presentar datos inventados como reales**, y el día que
se conecte un modelo de verdad ese aviso desaparece solo.

Si prefieres enseñar el comportamiento sin relleno, arranca con `AI_MOCK_RICH=0`: entonces cada
agente devuelve un informe vacío y la UI dice qué falta y por qué.

### h) Lo que hay debajo (si el público es técnico)

- **http://localhost:8001/docs** — el contrato completo. De ese `openapi.json` se generan los
  tipos de TypeScript del frontend; si alguien cambia una respuesta y no lo regenera, la
  compilación falla.
- **`GET /api/audit/verify`** — la auditoría está encadenada por hash y de solo anexado; el
  endpoint recalcula la cadena y dice si alguien tocó una fila.
- **Reiniciar el backend** (cerrar su ventana y volver a lanzar `demo.bat`): los datos siguen,
  los identificadores no se repiten y una ejecución a medias se reanudaría por donde iba.

---

## 3. Qué es real y qué no (por si preguntan)

| Parte | Estado |
|---|---|
| Requerimientos, adjuntos, clasificación de PHI | Real, en PostgreSQL y cifrado en reposo |
| Plan, avisos y bloqueos | Real, reglas deterministas + opción asistida por el modelo |
| Motor de ejecución, traza, cancelación, reanudación | Real |
| Coste y tokens por llamada | Real (con `mock` valen 0) |
| Auditoría encadenada | Real |
| **Análisis de los agentes** | **Simulado**: contenido de ejemplo del proveedor `mock` (avisado en pantalla) |
| Conexión con repositorios de verdad | Real: el servidor clona, calcula el diff y aplica reglas deterministas |
| Bóveda de secretos (Gobierno) | Real: cifrada en la base, con rotación, revocación y auditoría |
| Gobierno (resto), Monitor, edición de prompts | Pantallas con datos de ejemplo |
| Usuarios, sesión y permisos | Real: contraseñas con scrypt, sesión con caducidad, permisos comprobados en el servidor |

El pie de la aplicación lo dice también, para que no dependa de que tú te acuerdes.

### ¿Se puede enseñar con un modelo de verdad?

Sí, pero piénsalo antes:

```
set AI_PROVIDER=openrouter     (o anthropic)
```

Dos avisos: **cuesta dinero** y, con un requerimiento clasificado con PHI, el guardarraíl
**bloquea** el proveedor sin BAA. Eso último es en sí una buena demo: enséñalo a propósito.

---

## 4. Preguntas que van a hacer

**«¿Esto llama a un modelo de verdad?»**
Con la configuración de la demo, no: `mock`. La capa de IA está hecha y probada, con Anthropic
por SDK oficial y OpenRouter por HTTP; se cambia con una variable de entorno.

**«¿Y si el modelo devuelve cualquier cosa?»**
Cada agente tiene un esquema de salida declarado y no editable. Si la respuesta no lo cumple, se
reintenta una vez y, si no converge, ese agente falla y el dictamen lo refleja. Nunca llega al
consolidador una salida inválida.

**«¿Qué pasa con los datos de pacientes?»**
Hoy: el contenido va cifrado en reposo, un proveedor sin BAA no puede procesar un requerimiento
con PHI, el valor de un identificador no se guarda ni se muestra nunca, y el dictamen no puede
aprobar sin informe de Privacidad. Y lo más importante: **nada sale hacia un proveedor sin pasar
por la redacción** (ORQ-20). El prompt, el contexto y lo que devuelve cada herramienta se revisan
en el servidor, y el valor detectado se sustituye por un marcador con el tipo (`«PHI:ssn»`), de
forma que el modelo ve que ahí había algo pero no recibe el dato.

Esto se puede enseñar en directo: crea un requerimiento con un SSN o un número de historia clínica
inventados en la descripción, ejecútalo y mira la traza. Sale un evento **PHI redactada** por
agente con el recuento por tipo. Lo que la persona escribió sigue en su requerimiento (es su
registro, cifrado en reposo); lo que no sale de la casa es hacia el proveedor.

Lo que todavía falta de esta parte: las reglas deterministas ya están en el servidor, pero el
agente de Privacidad todavía no cruza sus reglas con los archivos del repositorio conectado (llega con su propia tarea).

**«¿Cuánto cuesta una revisión?»**
Cada llamada registra tokens y coste; hay techo por ejecución que la corta al superarse. Con
`mock` todo vale 0.

**«¿Por qué el Monitor tiene datos inventados?»**
Porque el consumo por usuario y los usuarios reales son tareas que aún no están (ORQ-29, ORQ-5).
Está marcado como ejemplo a propósito en vez de disimularlo.

---

## 5. Si algo va mal

| Síntoma | Causa y arreglo |
|---|---|
| No puedo entrar | La cuenta se crea solo si la base no tiene ninguna. Mira la ventana del backend: dice si la sembró o si faltan `ADMIN_EMAIL`/`ADMIN_PASSWORD` |
| «La sesión se cerró por inactividad» | Es lo normal tras 30 minutos sin tocar nada. Se ajusta con `SESSION_IDLE_MINUTES` |
| La lista dice «El servicio no responde» | El backend no está arriba. Mira su ventana; `uvicorn orq.main:app --port 8001` dentro de `backend/` |
| La página sale rota con errores de *chunk* | Se lanzó `next build` con `next dev` abierto: comparten `.next`. Borra `frontend\.next` y arranca de nuevo |
| «No se pudo hablar con la API» al sembrar | El backend tardó más de 90 s en arrancar. Vuelve a ejecutar `backend\.venv\Scripts\python.exe scripts\seed_demo.py` |
| Los datos desaparecen al reiniciar | Docker no estaba levantado y la demo corrió en memoria |
| La lista sale vacía pero la base tiene filas | Cambió la clave de cifrado. Recupera `%LOCALAPPDATA%\orq-demo\clave.txt` o arranca con `demo.bat limpio` |
| La traza pasa demasiado rápido | Sube `AI_MOCK_DELAY_MS` (1500 por defecto en `demo.bat`) |
| Quiero informes vacíos en vez de ejemplos | `set AI_MOCK_RICH=0` antes de `demo.bat` |

---

## 6. Cerrar

Cierra las dos ventanas de consola. El contenedor de PostgreSQL sigue vivo para la próxima:

```
docker stop orq-postgres
```
