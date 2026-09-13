# Plan de Implementación: Mi Amigo Max

## Descripción general

Implementación incremental del agente conversacional "Mi Amigo Max" sobre Python 3.11+, Strands Agents SDK, Amazon Bedrock (Claude) y SQLite. El plan sigue el orden de dependencias naturales del sistema: infraestructura de base de datos → herramientas del agente → núcleo del agente → interfaces de usuario → documentación y pruebas.

---

## Tareas

- [ ] 1. Configuración inicial del proyecto
  - [ ] 1.1 Crear la estructura de directorios y archivos de inicialización
    - Crear los directorios `agent/`, `db/`, `docs/`, `tests/` y los archivos `__init__.py` correspondientes en `agent/` y `db/`
    - Crear `.gitignore` incluyendo `.env`, `*.db`, `__pycache__/`, `.venv/`, `*.pyc`
    - Crear `requirements.txt` con versiones fijas (`==`) para: `strands-agents`, `boto3`, `botocore`, `python-dotenv`, `streamlit`, `hypothesis`, `pytest`, `pytest-mock`
    - Crear `.env.example` con `AWS_REGION`, `BEDROCK_MODEL_ID`, `DB_PATH` y `LOG_LEVEL` con valores de ejemplo no sensibles y descripción de una línea por variable
    - _Requisitos: 7.1, 7.2, 7.4, 12.3_

- [ ] 2. Capa de base de datos
  - [ ] 2.1 Implementar `db/setup.py` — inicialización del schema SQLite
    - Implementar la función `inicializar_db(ruta_db: str) -> None` con docstring en español
    - Ejecutar `PRAGMA foreign_keys = ON` en la conexión
    - Crear en una única transacción atómica las tablas: `usuarios`, `sesiones`, `mensajes`, `habitos`, `flags_derivacion` con sus claves primarias `INTEGER PRIMARY KEY AUTOINCREMENT`, claves foráneas a `usuarios(id)`, restricciones `NOT NULL` en todos los campos obligatorios y `CHECK` constraints según el diseño
    - Crear los índices: `idx_mensajes_usuario`, `idx_habitos_usuario`, `idx_sesiones_usuario`, `idx_flags_usuario_sesion`
    - Invocar `inicializar_db` automáticamente si el archivo `.db` no existe al importar el módulo
    - _Requisitos: 6.1, 6.2, 13.4_

  - [ ]* 2.2 Escribir pruebas unitarias para `db/setup.py`
    - Verificar que el schema completo se crea correctamente en una DB en memoria
    - Verificar que la inicialización es idempotente (ejecutar dos veces no lanza error)
    - Verificar que `PRAGMA foreign_keys = ON` está activo
    - Archivo: `tests/test_db_setup.py`
    - _Requisitos: 6.1, 6.2_

  - [ ] 2.3 Implementar `db/models.py` — funciones de acceso a datos
    - Implementar con docstring en español (qué hace, parámetros, retorno) cada función del contrato de diseño:
      - `crear_usuario(nombre: str) -> int`
      - `obtener_usuario_por_nombre(nombre: str) -> dict | None`
      - `actualizar_nivel_complejidad(usuario_id: int, nivel: str) -> None`
      - `crear_sesion(usuario_id: int, canal: str) -> int`
      - `cerrar_sesion(sesion_id: int) -> None`
      - `contar_sesiones_hoy(usuario_id: int) -> int`
      - `guardar_mensaje(sesion_id: int, rol: str, contenido: str) -> None` — implementar la lógica de límite de 50 mensajes por usuario en una transacción atómica: si `COUNT(*) >= 50` para ese `usuario_id`, eliminar el más antiguo antes de insertar
      - `obtener_historial(usuario_id: int, limite: int = 50) -> list[dict]`
      - `obtener_ultimos_n_mensajes(usuario_id: int, n: int) -> list[dict]`
      - `insertar_habito(usuario_id: int, categoria: str, valor: float, unidad: str) -> None`
      - `obtener_habitos_periodo(usuario_id: int, dias: int) -> list[dict]`
      - `insertar_flag_derivacion(usuario_id: int, nivel_riesgo: str, frases_detectadas: list[str], accion_tomada: str) -> None`
      - `tiene_flag_derivacion_activo(usuario_id: int, sesion_id: int) -> bool`
    - Usar `try/except` específicos capturando `sqlite3.OperationalError` e `sqlite3.IntegrityError` (no `Exception` genérica), devolver mensajes de error en español con la ruta del archivo afectado
    - _Requisitos: 6.1, 6.3, 6.4, 6.5, 13.1, 13.2_

  - [ ]* 2.4 Escribir pruebas de propiedad para `db/models.py`
    - **Propiedad 4: Invariante de límite de mensajes por usuario**
      - `@given(st.integers(min_value=51, max_value=200))` — insertar N mensajes para el mismo usuario y verificar que `COUNT(*) == 50` siempre
      - **Valida: Requisito 6.5**
    - Archivo: `tests/test_db_models.py`

  - [ ]* 2.5 Escribir pruebas unitarias adicionales para `db/models.py`
    - Crear usuario y recuperarlo por nombre
    - Cerrar sesión actualiza `timestamp_fin` y `duracion_minutos`
    - `contar_sesiones_hoy` devuelve 0 para usuario sin sesiones del día
    - `tiene_flag_derivacion_activo` devuelve `False` cuando no hay flags
    - `obtener_habitos_periodo` devuelve lista vacía si no hay registros
    - Archivo: `tests/test_db_models.py`
    - _Requisitos: 6.3, 6.4, 6.5_

- [ ] 3. Checkpoint — Verificar capa de base de datos
  - Asegurar que todos los tests de `test_db_setup.py` y `test_db_models.py` pasen. Preguntar al usuario si hay dudas antes de continuar.

- [ ] 4. Herramientas del agente (`agent/tools.py`)
  - [ ] 4.1 Implementar `registrar_habito`
    - Decorar con el decorator de Tool del Strands SDK
    - Docstring en español: qué hace, parámetros, retorno
    - Validar `categoria` ∈ `{"sueño", "alimentación", "actividad"}`, `valor > 0` y dentro del rango por categoría (sueño: 0–24, alimentación: 0–20, actividad: 0–600), `unidad` no vacía
    - Si validación falla: devolver `{"ok": false, "error": "…rango válido…"}` sin persistir
    - Si éxito: llamar `db/models.py::insertar_habito` y devolver `{"ok": true, "habito_id": …, "mensaje": "…"}`
    - Si error de DB: capturar `sqlite3.OperationalError` y devolver `{"error": "…en español…"}`
    - _Requisitos: 2.1, 2.3, 2.7, 11.1, 11.3, 13.1, 13.2_

  - [ ]* 4.2 Escribir prueba de propiedad para `registrar_habito`
    - **Propiedad 2: Round-trip de persistencia de hábitos**
      - `@given(st.builds(...))` con categoría válida, valor en rango y unidad no vacía: persistir con `registrar_habito` y verificar presencia en `obtener_resumen_habitos`
      - **Valida: Requisitos 2.3, 2.4, 11.3**
    - **Propiedad 3: Rechazo de valores de hábito fuera de rango**
      - `@given(st.floats())` fuera de rangos válidos: verificar que `registrar_habito` devuelve `ok=false` y que la DB no contiene el registro
      - **Valida: Requisito 2.7**
    - Archivo: `tests/test_tools.py`

  - [ ] 4.3 Implementar `obtener_resumen_habitos`
    - Decorar con Tool del Strands SDK; docstring en español
    - Parámetros: `usuario_id: int`, `dias: int` (1–30, por defecto 7)
    - Llamar `db/models.py::obtener_habitos_periodo` y calcular promedios diarios por categoría
    - Si hay datos: devolver estructura `{"ok": true, "periodo_dias": …, "resumen": {…}}` con `promedio_diario`, `unidad`, `dias_registrados` por categoría
    - Si no hay datos: devolver `{"ok": true, "periodo_dias": …, "resumen": {}, "mensaje": "No hay registros…"}` 
    - Si error de DB: devolver `{"error": "…"}`
    - _Requisitos: 2.2, 2.4, 2.8, 11.1, 13.1_

  - [ ] 4.4 Implementar `detectar_senal_riesgo`
    - Decorar con Tool del Strands SDK; docstring en español
    - Parámetros: `usuario_id: int`, `texto_turno: str`, `historial: list[str]`
    - Construir prompt especializado con el texto del turno y los últimos 5 mensajes del historial para clasificar: `"bajo"`, `"medio"` o `"alto"`
    - Aplicar timeout de 3 segundos a la llamada interna; si timeout o error: devolver `{"nivel": "alto", "frases_detectadas": ["[ERROR INTERNO: análisis no disponible — aplicando protocolo de seguridad]"]}`
    - Devolver siempre `{"nivel": "…", "frases_detectadas": […]}` (lista vacía si nivel es `"bajo"`)
    - _Requisitos: 3.2, 3.5, 3.7, 11.1, 11.4, 13.1_

  - [ ]* 4.5 Escribir prueba de propiedad para `detectar_senal_riesgo`
    - **Propiedad 5: Contrato de retorno de `detectar_senal_riesgo`**
      - `@given(st.text(), st.lists(st.text()))`: verificar que el resultado siempre tiene exactamente las claves `"nivel"` y `"frases_detectadas"`, que `nivel` ∈ `{"bajo","medio","alto"}` y `frases_detectadas` es una lista de strings
      - **Valida: Requisitos 3.5, 3.7, 11.4**
    - Archivo: `tests/test_tools.py`

  - [ ] 4.6 Implementar `sugerir_pausa`
    - Decorar con Tool del Strands SDK; docstring en español
    - Parámetros: `usuario_id: int`, `sugerencias_previas: list[str]`
    - Pool base de al menos 10 actividades predeterminadas (máx. 15 palabras cada una)
    - Seleccionar entre 3 y 5 sugerencias garantizando que no más de 2 coincidan con `sugerencias_previas`
    - Si la selección toma más de 3 segundos: devolver fallback predeterminado de 3 sugerencias con `"_fallback": true`
    - Devolver `{"sugerencias": […]}` con éxito
    - _Requisitos: 4.1, 4.2, 4.7, 11.1, 11.5, 13.1_

  - [ ]* 4.7 Escribir prueba de propiedad para `sugerir_pausa`
    - **Propiedad 7: Contrato de tamaño y contenido de `sugerir_pausa`**
      - `@given(st.lists(st.text(), max_size=5))`: verificar que el resultado contiene entre 3 y 5 sugerencias, cada una ≤ 15 palabras, y que no más de 2 coinciden con las previas
      - **Valida: Requisitos 4.2, 11.5**
    - Archivo: `tests/test_tools.py`

  - [ ] 4.8 Implementar `explicar_tema`
    - Decorar con Tool del Strands SDK; docstring en español
    - Parámetros: `usuario_id: int`, `tema: str` (no vacío, máx. 200 caracteres), `nivel: str` (`"básico"` o `"intermedio"`)
    - Nivel `"básico"`: oraciones de máx. 15 palabras, vocabulario cotidiano, sin términos técnicos no definidos
    - Nivel `"intermedio"`: hasta 3 términos técnicos, cada uno definido en la respuesta
    - Devolver explicación de máx. 200 palabras: `{"ok": true, "tema": …, "nivel": …, "explicacion": …, "fuente_sugerida": null}`
    - Si tema no disponible: `{"ok": false, "tema": …, "explicacion": null, "fuente_sugerida": "…"}` con fuente del conjunto definido en el diseño
    - Si error interno: `{"error": "…en español…"}`
    - _Requisitos: 5.1, 5.2, 5.5, 11.1, 11.6, 13.1_

  - [ ]* 4.9 Escribir prueba de propiedad para `explicar_tema`
    - **Propiedad 8: Contrato de longitud y nivel de `explicar_tema`**
      - `@given(st.text(min_size=1, max_size=200), st.sampled_from(["básico", "intermedio"]))`: verificar que la explicación devuelta tiene ≤ 200 palabras o que se devuelve `fuente_sugerida`
      - **Valida: Requisitos 5.2, 5.5, 11.6**
    - Archivo: `tests/test_tools.py`

  - [ ]* 4.10 Escribir prueba de propiedad de captura de errores en Tools
    - **Propiedad 9: Captura de errores en todas las Tools**
      - `@given(st.sampled_from([registrar_habito, obtener_resumen_habitos, detectar_senal_riesgo, sugerir_pausa, explicar_tema]))` con inyección de excepciones: verificar que ninguna Tool propaga la excepción y que siempre devuelve `{"error": "…string en español…"}`
      - **Valida: Requisitos 11.7, 13.2**
    - Archivo: `tests/test_tools.py`

- [ ] 5. Checkpoint — Verificar herramientas del agente
  - Asegurar que todos los tests de `tests/test_tools.py` pasen. Preguntar al usuario si hay dudas antes de continuar.

- [ ] 6. Núcleo del agente (`agent/max_agent.py`)
  - [ ] 6.1 Definir el System Prompt
    - Crear o la constante `SYSTEM_PROMPT` en `agent/max_agent.py` o el archivo `agent/system_prompt.txt` leído al importar el módulo (inspeccionable sin ejecutar el agente)
    - El System Prompt debe incluir exactamente:
      - Sección `## Reglas de no enganche` con las tres prohibiciones numeradas del diseño
      - Sección `## Reglas de derivación humana` con los tres disparadores numerados del diseño
      - La instrucción literal: `"No te identifiques como terapeuta, médico, psicólogo ni ningún otro profesional de salud en ningún momento de la conversación."`
      - Reglas de tono: oraciones ≤ 20 palabras cuando el usuario use mensajes cortos (< 10 palabras)
      - Protocolos de hábitos y pausa tal como se especifican en el diseño
    - _Requisitos: 3.4, 4.4, 4.6, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 6.2 Implementar la clase `MaxAgent` y `create_agent`
    - Implementar `create_agent(usuario_id: int, nombre_usuario: str) -> MaxAgent` con docstring en español
    - Implementar `MaxAgent` con los métodos:
      - `__init__`: cargar System Prompt, instanciar el agente Strands con las 5 Tools y el modelo Bedrock configurado con `connect_timeout=10`, `read_timeout=30`, `retries={"max_attempts": 2}`; inicializar historial en memoria y temporizador de sesión; registrar sesión en `db/models.py`
      - `chat(self, mensaje_usuario: str) -> str`: procesar un turno (invocar `detectar_senal_riesgo`, gestionar flags de derivación, controlar el temporizador de pausa a 30 y 60 minutos, verificar si es la 4.ª+ sesión del día y emitir mensaje de variedad en los primeros 3 turnos, invocar Bedrock, guardar mensajes en DB); devolver respuesta de Max como string
      - `cerrar_sesion(self) -> None`: actualizar `timestamp_fin` y `duracion_minutos` en la tabla `sesiones`
    - Cargar `AWS_REGION` y `BEDROCK_MODEL_ID` desde variables de entorno
    - _Requisitos: 1.1, 1.2, 3.1, 3.2, 3.3, 3.8, 4.1, 4.5, 4.8, 6.3, 6.4, 13.1, 13.5_

  - [ ]* 6.3 Escribir prueba de propiedad de validación de nombres en `conftest.py` / `test_cli.py`
    - **Propiedad 1: Validación de nombres de usuario**
      - `@given(st.text())`: verificar que nombres con longitud < 1 o > 50 son rechazados, y que nombres con longitud en [1,50] son aceptados y persistidos
      - **Valida: Requisitos 1.4, 1.5**
    - Archivo: `tests/test_cli.py`

  - [ ]* 6.4 Escribir prueba de propiedad de round-trip de nivel de complejidad
    - **Propiedad 10: Round-trip de nivel de complejidad del usuario**
      - `@given(st.sampled_from(["básico", "intermedio"]))`: persistir el nivel, abrir nueva sesión y verificar que se recupera el mismo nivel sin recalcular
      - **Valida: Requisito 5.4**
    - Archivo: `tests/test_db_models.py`

  - [ ]* 6.5 Escribir prueba de propiedad de persistencia de flag de derivación
    - **Propiedad 6: Persistencia de flag de derivación ante riesgo alto**
      - `@given(st.integers(min_value=1), st.text(min_size=1))`: simular turno que resulte en nivel `"alto"` y verificar que `flags_derivacion` contiene el registro con todos los campos requeridos antes de que `chat()` retorne
      - **Valida: Requisitos 3.2, 3.6**
    - Archivo: `tests/test_tools.py`

- [ ] 7. Checkpoint — Verificar núcleo del agente
  - Asegurar que todos los tests relacionados con `max_agent.py` pasen. Preguntar al usuario si hay dudas antes de continuar.

- [ ] 8. Interfaz CLI (`app.py`)
  - [ ] 8.1 Implementar `app.py` — punto de entrada CLI
    - Implementar `main() -> None` con docstring en español
    - Al inicio: llamar `load_dotenv()`, verificar variables de entorno requeridas (`AWS_REGION`, `BEDROCK_MODEL_ID`, `DB_PATH`); si faltan, mostrar lista de nombres de variables faltantes y referencia a `.env.example`, y terminar con `sys.exit(1)` sin mostrar stack trace
    - Llamar `db/setup.py::inicializar_db(DB_PATH)` si la DB no existe; si falla, mostrar mensaje con ruta y posible causa, terminar con `sys.exit(1)`
    - Parsear `--usuario` con `argparse`; si no se proporciona, solicitar el nombre interactivamente
    - Validar nombre (1–50 caracteres); si inválido, mostrar rango válido y volver a solicitar sin iniciar sesión
    - Crear o recuperar usuario en DB mediante `db/models.py`
    - Crear instancia `MaxAgent` via `create_agent`
    - Ejecutar el bucle de conversación:
      - Mostrar prefijo `Max:` para respuestas del agente y `<nombre>:` para el usuario
      - Si el usuario escribe `salir` o `exit` (case-insensitive): llamar `cerrar_sesion()`, mostrar despedida ≤ 20 palabras sin frases de regreso inmediato, terminar con `sys.exit(0)`
      - Si se recibe `KeyboardInterrupt`: llamar `cerrar_sesion()`, mostrar despedida, terminar con `sys.exit(0)` sin traceback
      - Si Bedrock devuelve error HTTP o de red: capturar, mostrar mensaje en español indicando problema de conexión, continuar el bucle sin terminar el proceso
    - _Requisitos: 1.3, 1.4, 1.5, 1.6, 7.1, 7.3, 8.1, 8.2, 8.3, 8.4, 8.5, 13.2_

  - [ ]* 8.2 Escribir pruebas unitarias para `app.py`
    - Primera sesión: verificar mensaje de bienvenida con nombre, propósito y límites (50–150 palabras)
    - Sesión subsiguiente: verificar saludo corto con nombre registrado (≤ 30 palabras)
    - Comando `salir`/`exit`: verificar actualización de DB y código de salida 0
    - `KeyboardInterrupt`: verificar actualización de DB y código de salida 0 sin traceback
    - Variables de entorno faltantes: verificar lista de nombres faltantes y referencia a `.env.example`
    - Error HTTP de Bedrock: verificar que el proceso continúa y muestra mensaje en español
    - Archivo: `tests/test_cli.py`
    - _Requisitos: 1.1, 1.2, 7.3, 8.3, 8.4, 8.5_

- [ ] 9. Interfaz Streamlit (`streamlit_app.py`)
  - [ ] 9.1 Implementar `streamlit_app.py` — interfaz web para demo
    - Importar y usar directamente `agent/max_agent.py` y `db/` sin reimplementar lógica
    - Gestionar estado en `st.session_state` con las claves: `usuario_id`, `nombre_usuario`, `sesion_id`, `agent`, `historial`, `inicializado`
    - Si no inicializado: mostrar campo de texto para que el usuario ingrese su nombre, validar y crear/recuperar usuario en DB, crear instancia `MaxAgent`
    - Mostrar historial con `st.chat_message`: mensajes de Max alineados a la izquierda con fondo diferenciado, mensajes del usuario alineados a la derecha
    - Aceptar input con `st.chat_input`
    - Mostrar `st.spinner("Max está pensando...")` mientras se genera la respuesta
    - Si Bedrock devuelve error: capturar y mostrar el mensaje de error en español dentro del panel de chat como mensaje de Max, sin lanzar excepción no controlada
    - _Requisitos: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 10. Checkpoint — Verificar interfaces completas
  - Asegurar que `app.py` y `streamlit_app.py` funcionan con la DB y el agente. Ejecutar todos los tests hasta este punto. Preguntar al usuario si hay dudas antes de continuar.

- [ ] 11. Documentación del proyecto
  - [ ] 11.1 Crear `README.md` en español
    - Secciones en este orden: descripción del proyecto, para quién es, cómo funciona (≤ 150 palabras), prerrequisitos, instrucciones de instalación numeradas, instrucciones de uso (CLI y Streamlit), diagrama de arquitectura en bloque Mermaid embebido, sección "Ética y diseño responsable" describiendo regla de no enganche y regla de derivación humana, advertencias éticas
    - _Requisitos: 12.1, 12.7_

  - [ ] 11.2 Crear `ARCHITECTURE.md` con diagrama Mermaid
    - Incluir al menos un diagrama Mermaid en bloque fenced que represente el flujo completo: `Usuario → CLI/Streamlit_UI → Max → Strands_SDK → Bedrock_Client → Tools → SQLite_DB`, con etiquetas en español
    - _Requisitos: 12.4_

  - [ ] 11.3 Crear `LICENSE` MIT 2025
    - Texto completo de la licencia MIT con año 2025 y nombre del titular del copyright
    - _Requisitos: 12.2_

  - [ ] 11.4 Crear `agentcore_config.md`
    - Instrucciones numeradas paso a paso para desplegar Max en AgentCore
    - Nota destacada al inicio indicando que el despliegue en AgentCore es opcional y que el sistema funciona localmente sin él
    - _Requisitos: 12.5_

  - [ ] 11.5 Crear `docs/demo_script.md`
    - Guion completo de 5 minutos con las secciones y tiempos: (1) Presentación del problema (1 min), (2) Para quién es la solución (30 s), (3) Por qué importa (30 s), (4) Demo en vivo paso a paso (2 min 30 s), (5) Cierre (30 s)
    - _Requisitos: 12.6_

- [ ] 12. Fixture de pruebas y configuración final (`tests/conftest.py`)
  - [ ] 12.1 Implementar `tests/conftest.py` con fixtures compartidos
    - Fixture `db_en_memoria`: crea una DB SQLite en memoria, ejecuta `inicializar_db` y la cierra al finalizar el test
    - Fixture `usuario_test`: crea un usuario de prueba en la DB en memoria y devuelve su `usuario_id`
    - Fixture `agente_mock`: crea un `MaxAgent` con el cliente Bedrock mockeado (sin llamadas reales a AWS)
    - _Requisitos: 13.2_

- [ ] 13. Checkpoint final — Todos los tests
  - Ejecutar la suite completa con `pytest tests/ -v`. Asegurar que todos los tests pasan, incluyendo las 10 pruebas de propiedades con Hypothesis. Preguntar al usuario si hay dudas antes de cerrar.

---

## Notas

- Las tareas marcadas con `*` son opcionales y pueden saltarse para un MVP más rápido, pero su ejecución garantiza las 10 propiedades de corrección definidas en `design.md`
- Cada tarea referencia requisitos específicos para trazabilidad completa
- Los checkpoints validan el avance incremental antes de pasar al siguiente bloque
- Las pruebas de propiedades usan Hypothesis con `@settings(max_examples=100)` mínimo
- Ninguna función en `agent/tools.py` ni `agent/max_agent.py` debe contener `pass`, `"TODO"` ni cuerpos vacíos al completar las tareas
- El archivo `.env` nunca se debe subir al repositorio (está en `.gitignore`)

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "2.5", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3"] },
    { "id": 5, "tasks": ["4.4", "4.6", "4.8"] },
    { "id": 6, "tasks": ["4.5", "4.7", "4.9", "4.10"] },
    { "id": 7, "tasks": ["6.1"] },
    { "id": 8, "tasks": ["6.2"] },
    { "id": 9, "tasks": ["6.3", "6.4", "6.5", "8.1"] },
    { "id": 10, "tasks": ["8.2", "9.1"] },
    { "id": 11, "tasks": ["11.1", "11.2", "11.3", "11.4", "11.5", "12.1"] }
  ]
}
```
