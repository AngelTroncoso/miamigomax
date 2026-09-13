# Requirements Document

## Introduction

"Mi Amigo Max" es un agente conversacional de inteligencia artificial diseñado para acompañar 24/7 a personas que viven solas o que requieren apoyo cotidiano, con especial atención a adultos mayores. Max no busca maximizar el tiempo de uso ni generar dependencia; su propósito es proporcionar compañía genuina, seguimiento suave de hábitos, acompañamiento emocional básico con derivación oportuna a humanos o profesionales, y educación contextual adaptada al nivel del usuario.

El sistema se construye sobre Python 3.11+, el SDK de Strands Agents, Amazon Bedrock (Claude) como proveedor de modelo, y SQLite para persistencia local. La interfaz principal es una CLI (`app.py`) complementada con una interfaz web mínima en Streamlit para demostraciones. El proyecto se enmarca en la pista "Everyday Agents" de la hackatón de Strands Agents / AWS.

---

## Glossary

- **Max**: El agente conversacional de IA que da nombre al proyecto.
- **Usuario**: Persona que interactúa con Max, típicamente un adulto mayor o alguien que vive solo.
- **Strands_SDK**: El SDK de Strands Agents utilizado como framework del agente.
- **Bedrock_Client**: El cliente de Amazon Bedrock que invoca el modelo Claude.
- **SQLite_DB**: La base de datos SQLite que persiste hábitos, conversaciones y flags de derivación.
- **CLI**: La interfaz de línea de comandos implementada en `app.py`.
- **Streamlit_UI**: La interfaz web mínima construida con Streamlit, usada para el video de demo.
- **Habit_Tracker**: El componente responsable del registro y consulta de hábitos (sueño, alimentación, actividad).
- **Risk_Detector**: El componente que evalúa señales de riesgo emocional o físico en la conversación.
- **Pause_Mode**: El modo de Max que sugiere al Usuario actividades fuera de la aplicación y limita activamente la duración de la sesión.
- **Derivación**: Acción de Max de indicar explícitamente al Usuario que contacte a un familiar, cuidador o profesional de salud.
- **Tool**: Función nativa del Strands_SDK que Max puede invocar para realizar acciones concretas.
- **System_Prompt**: Instrucciones permanentes que definen el comportamiento, límites éticos y reglas de derivación de Max.
- **AgentCore**: Plataforma de despliegue gestionado de agentes de AWS (uso opcional documentado).
- **Flag_Derivacion**: Registro en SQLite_DB que indica que se detectó una señal de riesgo y se activó una Derivación.
- **Sesion**: Una interacción continua del Usuario con Max desde que inicia hasta que cierra la conversación.

---

## Requirements

---

### Requisito 1: Inicio y presentación del agente

**Historia de usuario:** Como Usuario nuevo, quiero que Max se presente con un lenguaje sencillo y cálido al iniciar la primera conversación, para que entienda para qué sirve y qué no hace.

#### Criterios de aceptación

1. WHEN el Usuario inicia una Sesión por primera vez, THE Max SHALL presentarse con su nombre, propósito de acompañamiento emocional y límites explícitos (no es un médico, no reemplaza vínculos humanos) en un mensaje de bienvenida de entre 50 y 150 palabras.
2. WHEN el Usuario inicia una Sesión subsiguiente, THE Max SHALL saludar al Usuario por su nombre registrado y retomar el contexto de la última Sesión en no más de dos oraciones de hasta 30 palabras en total.
3. WHEN el Usuario ejecuta el CLI sin proporcionar el nombre como argumento, THE CLI SHALL solicitar el nombre del Usuario de forma interactiva antes de iniciar la conversación.
4. IF el nombre proporcionado por el Usuario tiene menos de 1 carácter o más de 50 caracteres, THEN THE CLI SHALL mostrar un mensaje de error indicando el rango válido y volver a solicitar el nombre sin iniciar la conversación.
5. IF el nombre del Usuario no está registrado en SQLite_DB, THEN THE CLI SHALL persistir el nombre en SQLite_DB antes de iniciar la conversación.
6. IF SQLite_DB no está disponible al intentar leer o escribir el nombre del Usuario, THEN THE CLI SHALL mostrar un mensaje de error indicando que no es posible iniciar la sesión y terminar sin iniciar la conversación.

---

### Requisito 2: Seguimiento de hábitos

**Historia de usuario:** Como Usuario, quiero registrar mis hábitos de sueño, alimentación y actividad física de forma conversacional, para que Max pueda darme sugerencias suaves basadas en mis patrones reales.

#### Criterios de aceptación

1. WHEN el Usuario menciona información sobre sueño, alimentación o actividad física durante la conversación, THE Habit_Tracker SHALL invocar la Tool `registrar_habito` con la categoría, valor y marca de tiempo correspondientes.
2. WHEN el Usuario solicita un resumen de sus hábitos, THE Habit_Tracker SHALL invocar la Tool `obtener_resumen_habitos` y presentar los datos de los últimos 7 días expresando los resultados en unidades comprensibles (horas de sueño, porciones de comida, minutos de actividad) sin usar términos estadísticos como "desviación estándar" o "percentil".
3. THE `registrar_habito` Tool SHALL persistir cada registro en SQLite_DB con los campos: `usuario_id`, `categoria` (sueño / alimentación / actividad), `valor`, `unidad`, `timestamp`.
4. THE `obtener_resumen_habitos` Tool SHALL leer los registros de SQLite_DB y calcular promedios diarios por categoría para el período solicitado.
5. WHEN el promedio de horas de sueño del Usuario en los últimos 3 días es inferior a 6 horas, THE Max SHALL emitir exactamente un mensaje de sugerencia sobre higiene del sueño en el turno siguiente a la detección, sin incluir diagnósticos médicos y sin repetirlo en la misma Sesión.
6. WHEN el Usuario no registra ningún hábito durante 48 horas consecutivas, THE Max SHALL enviar exactamente un mensaje de recordatorio de registro al inicio de la siguiente Sesión, sin emitir juicios de valor sobre el comportamiento del Usuario, y no volverá a enviarlo hasta que pasen otras 48 horas sin registro.
7. IF la Tool `registrar_habito` recibe un valor fuera del rango válido para su categoría (sueño: 0–24 horas; alimentación: 0–20 porciones; actividad: 0–600 minutos), THEN THE Habit_Tracker SHALL rechazar el registro y solicitar al Usuario confirmación o corrección con un mensaje que indique el rango válido esperado.
8. IF la Tool `obtener_resumen_habitos` no encuentra registros para el período solicitado, THEN THE Max SHALL informar al Usuario que no hay datos disponibles para ese período y sugerir comenzar a registrar hábitos en la conversación actual.
9. IF SQLite_DB no está disponible durante la invocación de `registrar_habito` u `obtener_resumen_habitos`, THEN THE Max SHALL informar al Usuario con un mensaje de error claro en español e intentar preservar el dato en memoria para reintentarlo al recuperarse la conexión.

---

### Requisito 3: Acompañamiento emocional básico

**Historia de usuario:** Como Usuario que atraviesa un momento difícil, quiero que Max reconozca mis emociones y me oriente hacia apoyo real, para que no me sienta solo pero tampoco dependa únicamente de una IA.

#### Criterios de aceptación

1. WHEN el Usuario expresa emociones negativas (tristeza, angustia, soledad, miedo) durante la conversación, THE Max SHALL reconocer la emoción con empatía antes de cualquier otra respuesta en el mismo turno, sin incluir diagnósticos, pronósticos ni tratamientos médicos o psicológicos.
2. WHEN el Risk_Detector invoca la Tool `detectar_senal_riesgo` y el resultado indica nivel de riesgo "alto" (soledad extrema, síntomas físicos urgentes, o angustia sostenida detectada en 3 o más turnos consecutivos), THE Max SHALL activar la Derivación en el mismo turno indicando explícitamente al Usuario que contacte a un familiar, cuidador o servicio de emergencias, y persistir un Flag_Derivacion en SQLite_DB.
3. WHEN el Risk_Detector invoca `detectar_senal_riesgo` y el resultado indica nivel de riesgo "medio" (tristeza recurrente o aislamiento leve), THE Max SHALL ofrecer recursos de apoyo (líneas de escucha o sugerencia de contactar a alguien de confianza) como máximo una vez por Sesión activa.
4. THE Max SHALL incluir en el System_Prompt la regla explícita de que nunca simulará ser un profesional de salud mental ni intentará resolver situaciones de riesgo sin Derivación.
5. THE `detectar_senal_riesgo` Tool SHALL analizar el texto del turno actual y los últimos 5 turnos del historial para clasificar el nivel de riesgo como "bajo", "medio" o "alto", devolviendo el nivel junto con las frases del historial que determinaron esa clasificación, con un tiempo de respuesta máximo de 3 segundos.
6. IF `detectar_senal_riesgo` devuelve nivel "alto", THEN THE SQLite_DB SHALL registrar el Flag_Derivacion con `usuario_id`, `timestamp`, `nivel_riesgo`, `frases_detectadas` y `accion_tomada`, antes de que Max entregue su respuesta al Usuario en ese mismo turno.
7. IF `detectar_senal_riesgo` no puede completar el análisis por error interno o tiempo de respuesta superior a 3 segundos, THEN THE Max SHALL tratar el resultado como nivel de riesgo "alto" y aplicar el protocolo de Derivación del criterio 2.
8. WHILE una Sesión activa tiene un Flag_Derivacion persistido, THE Max SHALL incluir en cada respuesta un recordatorio de que el Usuario puede contactar a un familiar, cuidador o servicio de emergencias, sin reemplazar el contenido principal de la respuesta.

---

### Requisito 4: Modo Pausa y anti-enganche

**Historia de usuario:** Como Usuario, quiero que Max me recuerde hacer pausas y me sugiera actividades fuera de la app, para que la IA no reemplace mis interacciones humanas ni mis actividades cotidianas.

#### Criterios de aceptación

1. WHEN una Sesión supera los 30 minutos continuos de conversación, THE Max SHALL invocar la Tool `sugerir_pausa` y presentar al Usuario al menos una actividad concreta fuera de la aplicación (llamar a alguien, salir a caminar, preparar algo de comer).
2. THE `sugerir_pausa` Tool SHALL devolver una lista de al menos 3 y no más de 5 sugerencias de actividades fuera de la aplicación, y no más de 2 sugerencias de la sesión anterior podrán repetirse en la sesión siguiente.
3. WHEN el Usuario acepta la sugerencia de pausa, THE Max SHALL cerrar la Sesión activa con un mensaje de despedida de tono cálido y no más de 30 palabras, sin incluir frases que inviten al Usuario a regresar de inmediato a la aplicación.
4. THE System_Prompt SHALL contener la regla explícita de que Max no debe generar respuestas diseñadas para prolongar la conversación ni crear urgencia artificial para que el Usuario continúe interactuando.
5. WHEN el Usuario inicia la cuarta Sesión o posterior en el mismo día calendario, THE Max SHALL incluir, dentro de los primeros 3 turnos de conversación, un mensaje que mencione que es saludable variar las fuentes de compañía y apoyo, sin interrumpir el hilo conversacional del Usuario.
6. THE Max SHALL omitir frases de cierre diseñadas para incentivar la vuelta inmediata a la aplicación (por ejemplo, "¡Vuelve pronto!", "¡No puedo esperar a hablar contigo de nuevo!").
7. IF la Tool `sugerir_pausa` no devuelve una respuesta en menos de 3 segundos, THEN THE Max SHALL presentar al Usuario al menos una actividad concreta predeterminada fuera de la aplicación sin esperar el resultado de la Tool.
8. WHEN una Sesión supera los 60 minutos continuos de conversación, THE Max SHALL invocar nuevamente la Tool `sugerir_pausa` y presentar la sugerencia de pausa al Usuario, independientemente de si una sugerencia anterior fue rechazada.

---

### Requisito 5: Educación contextual

**Historia de usuario:** Como Usuario, quiero que Max me explique temas cotidianos (salud, tecnología, trámites, recetas) en un lenguaje adaptado a mí, para que pueda aprender cosas útiles sin sentirme abrumado.

#### Criterios de aceptación

1. WHEN el Usuario solicita explicación de un tema durante la conversación, THE Max SHALL invocar la Tool `explicar_tema` con el tema identificado y el nivel de complejidad inferido del historial del Usuario, en un plazo máximo de 3 segundos desde la recepción de la solicitud.
2. THE `explicar_tema` Tool SHALL devolver una explicación de no más de 200 palabras, sin términos técnicos que no hayan sido definidos previamente en la Sesión actual, adaptada al nivel de complejidad solicitado ("básico" o "intermedio"), donde "básico" usa oraciones de máximo 15 palabras y vocabulario del habla cotidiana, e "intermedio" puede incluir hasta 3 términos técnicos por explicación siempre que cada uno sea definido en la misma respuesta.
3. WHEN el Usuario indica que no entendió una explicación, THE Max SHALL reformularla en el turno siguiente incluyendo al menos un ejemplo concreto referenciado a actividades o situaciones de la vida cotidiana (p. ej., cocina, transporte, compras), sin repetir el texto de la explicación anterior.
4. THE Max SHALL inferir el nivel de complejidad del Usuario a partir del promedio de longitud de sus mensajes y la proporción de términos técnicos detectados en los últimos 10 mensajes de la Sesión actual, y SHALL almacenar el nivel detectado ("básico" o "intermedio") en SQLite_DB asociado al identificador de Usuario para ser recuperado en Sesiones futuras.
5. IF la Tool `explicar_tema` no puede generar una explicación para el tema solicitado, THEN THE Max SHALL informar al Usuario mediante un mensaje indicando que el tema no está disponible y SHALL sugerir al menos una fuente de consulta alternativa del siguiente conjunto según el tema: familiar de confianza, médico o farmacéutico (temas de salud), página web oficial del organismo competente (trámites), o técnico especialista (tecnología).
6. IF el historial de la Sesión actual contiene menos de 3 mensajes del Usuario, THEN THE Max SHALL asumir el nivel de complejidad "básico" para invocar la Tool `explicar_tema` hasta que disponga de datos suficientes para inferir el nivel según el criterio 4.

---

### Requisito 6: Persistencia y gestión de datos

**Historia de usuario:** Como desarrollador, quiero que SQLite_DB almacene de forma organizada todos los datos necesarios, para que Max mantenga contexto entre Sesiones sin depender de servicios externos.

#### Criterios de aceptación

1. THE SQLite_DB SHALL contener al menos las tablas: `usuarios`, `habitos`, `sesiones`, `mensajes`, `flags_derivacion`, cada una con clave primaria entera autoincremental y restricciones NOT NULL en todos los campos obligatorios.
2. THE SQLite_DB SHALL ser inicializada automáticamente por el script `db/setup.py` si no existe el archivo de base de datos en la ruta configurada, creando todas las tablas y sus índices en una única transacción atómica.
3. WHEN Max inicia una Sesión, THE SQLite_DB SHALL registrar el inicio de Sesión en la tabla `sesiones` con `usuario_id`, `timestamp_inicio` y `canal` ("cli" o "streamlit") en un plazo máximo de 1 segundo.
4. WHEN Max cierra una Sesión, THE SQLite_DB SHALL actualizar el registro de Sesión con `timestamp_fin` y `duracion_minutos` calculado como la diferencia entre `timestamp_fin` y `timestamp_inicio` expresada en minutos enteros.
5. THE SQLite_DB SHALL almacenar los últimos 50 mensajes por Usuario en la tabla `mensajes`; cuando se inserte un mensaje nuevo que supere el límite de 50 para ese usuario, THE SQLite_DB SHALL eliminar el mensaje más antiguo del mismo usuario antes de insertar el nuevo.
6. IF el archivo de SQLite_DB no puede ser leído o escrito, THEN THE CLI SHALL mostrar un mensaje de error en español que incluya la ruta del archivo afectado y una posible causa (permisos, disco lleno), sin mostrar el stack trace de Python al Usuario.

---

### Requisito 7: Configuración y variables de entorno

**Historia de usuario:** Como desarrollador, quiero que todas las credenciales y parámetros de configuración se gestionen mediante variables de entorno documentadas, para que el proyecto sea seguro y reproducible en cualquier entorno.

#### Criterios de aceptación

1. THE Max SHALL leer al menos las variables `AWS_REGION`, `BEDROCK_MODEL_ID` y `DB_PATH` desde variables de entorno definidas en un archivo `.env` cargado mediante `python-dotenv` al inicio de la aplicación, antes de cualquier otra operación.
2. THE repositorio SHALL incluir un archivo `.env.example` que liste todas las variables de entorno requeridas con sus nombres exactos, una descripción de una línea por variable y un valor de ejemplo no sensible (p. ej., `AWS_REGION=us-east-1`).
3. IF una o más variables de entorno requeridas no están definidas al iniciar la aplicación, THEN THE CLI SHALL mostrar un mensaje de error en español que liste únicamente los nombres de las variables faltantes y referencie el archivo `.env.example`, sin imprimir los valores de las variables correctamente configuradas.
4. THE archivo `.env` SHALL estar listado en el archivo `.gitignore` del repositorio para prevenir la inclusión accidental de credenciales en el control de versiones.

---

### Requisito 8: Interfaz CLI

**Historia de usuario:** Como Usuario técnico, quiero interactuar con Max desde la línea de comandos con un flujo conversacional claro, para que pueda probar y usar el agente sin necesidad de una interfaz gráfica.

#### Criterios de aceptación

1. THE CLI SHALL aceptar el argumento `--usuario` para especificar el nombre del Usuario al iniciar; si no se proporciona, solicitará el nombre de forma interactiva.
2. THE CLI SHALL mostrar los mensajes de Max con el prefijo "Max:" y los mensajes del Usuario con el prefijo formado por el nombre del Usuario seguido de ":", en turnos claramente diferenciados en la salida estándar.
3. WHEN el Usuario escribe "salir" o "exit" (sin distinguir mayúsculas de minúsculas), THE CLI SHALL actualizar el registro de Sesión en SQLite_DB, mostrar un mensaje de despedida de no más de 20 palabras y terminar el proceso con código de salida 0.
4. WHEN el Usuario presiona Ctrl+C durante una Sesión activa, THE CLI SHALL capturar la señal de interrupción, actualizar el registro de Sesión en SQLite_DB con `timestamp_fin` y `duracion_minutos`, y terminar el proceso con código de salida 0 sin mostrar un traceback de Python.
5. IF el Bedrock_Client devuelve un error HTTP o de red durante la generación de respuesta, THEN THE CLI SHALL mostrar un mensaje de error en español indicando que hubo un problema de conexión, sugerir reintentar en unos momentos y continuar esperando la siguiente entrada del Usuario sin terminar el proceso.

---

### Requisito 9: Interfaz web Streamlit

**Historia de usuario:** Como evaluador de la hackatón, quiero ver una demo visual de Max en el navegador, para que pueda apreciar la experiencia de usuario sin necesidad de configurar un entorno de línea de comandos.

#### Criterios de aceptación

1. THE Streamlit_UI SHALL mostrar el historial de la conversación actual en un panel de chat donde los mensajes de Max aparecen alineados a la izquierda con fondo diferenciado y los mensajes del Usuario aparecen alineados a la derecha, usando los componentes nativos de chat de Streamlit (`st.chat_message`).
2. THE Streamlit_UI SHALL incluir un campo de texto de entrada (`st.chat_input`) para que el Usuario escriba sus mensajes y los envíe presionando Enter o haciendo clic en el botón de envío.
3. WHILE Max genera su respuesta, THE Streamlit_UI SHALL mostrar un indicador de actividad mediante `st.spinner` con el texto "Max está pensando..." hasta que la respuesta esté disponible.
4. THE Streamlit_UI SHALL importar y usar directamente las funciones de `agent/max_agent.py` y `db/` sin reimplementar la lógica del agente ni las operaciones de base de datos.
5. IF el Bedrock_Client devuelve un error durante la generación de respuesta en la Streamlit_UI, THEN THE Streamlit_UI SHALL mostrar el mensaje de error en español dentro del panel de chat como un mensaje de Max, sin lanzar una excepción no controlada que interrumpa la sesión de Streamlit.

---

### Requisito 10: System Prompt y reglas éticas del agente

**Historia de usuario:** Como responsable del proyecto, quiero que las reglas éticas de Max estén codificadas de forma explícita en el System Prompt, para que el comportamiento del agente sea predecible y auditable.

#### Criterios de aceptación

1. THE System_Prompt SHALL contener una sección titulada exactamente "Reglas de no enganche" que incluya al menos las siguientes tres prohibiciones numeradas: (1) no generar respuestas diseñadas para prolongar la Sesión, (2) no crear urgencia artificial para que el Usuario continúe interactuando, (3) no usar frases que incentiven el regreso inmediato a la aplicación.
2. THE System_Prompt SHALL contener una sección titulada exactamente "Reglas de derivación humana" que incluya al menos los siguientes tres disparadores numerados de Derivación obligatoria: (1) mención de daño a sí mismo o a otros, (2) síntomas físicos que requieran atención médica inmediata, (3) angustia sostenida detectada en 3 o más turnos consecutivos.
3. THE System_Prompt SHALL incluir la instrucción literal: "No te identifiques como terapeuta, médico, psicólogo ni ningún otro profesional de salud en ningún momento de la conversación."
4. THE System_Prompt SHALL especificar que Max debe usar un tono cálido y paciente, con oraciones de no más de 20 palabras cuando el Usuario use mensajes cortos (menos de 10 palabras), y puede usar oraciones más largas cuando el Usuario demuestre mayor elaboración en sus respuestas.
5. THE `agent/max_agent.py` SHALL cargar el System_Prompt desde una constante de cadena de texto definida en el mismo archivo `agent/max_agent.py` o desde un archivo `agent/system_prompt.txt` leído al inicializar el módulo, de modo que el texto del prompt sea inspeccionable sin ejecutar el agente.

---

### Requisito 11: Herramientas del agente (Tools)

**Historia de usuario:** Como desarrollador, quiero que las cinco Tools del agente estén implementadas con contratos claros de entrada y salida, para que Max pueda invocarlas de forma confiable en cualquier turno de conversación.

#### Criterios de aceptación

1. THE `agent/tools.py` SHALL definir exactamente las siguientes cinco funciones decoradas como Tools del Strands_SDK con sus nombres en snake_case: `registrar_habito`, `obtener_resumen_habitos`, `detectar_senal_riesgo`, `sugerir_pausa`, `explicar_tema`.
2. WHEN se inicializa la instancia del agente Max, THE Strands_SDK SHALL recibir la lista de las cinco Tools de `agent/tools.py` como argumento de configuración del agente.
3. WHEN la Tool `registrar_habito` es invocada, THE Tool SHALL validar que el parámetro `categoria` sea una cadena con valor "sueño", "alimentación" o "actividad"; que `valor` sea un número mayor que 0; y que `unidad` sea una cadena no vacía, antes de persistir el registro en SQLite_DB.
4. WHEN la Tool `detectar_senal_riesgo` es invocada, THE Tool SHALL devolver un diccionario Python serializable a JSON con exactamente dos claves: `nivel` con valor "bajo", "medio" o "alto", y `frases_detectadas` con valor de tipo lista de cadenas de texto (puede ser lista vacía si nivel es "bajo").
5. WHEN la Tool `sugerir_pausa` es invocada, THE Tool SHALL devolver un diccionario Python serializable a JSON con la clave `sugerencias` cuyo valor es una lista de entre 3 y 5 cadenas de texto, cada una describiendo una actividad fuera de la aplicación en no más de 15 palabras.
6. WHEN la Tool `explicar_tema` es invocada, THE Tool SHALL aceptar los parámetros `tema` (cadena no vacía) y `nivel` (cadena con valor "básico" o "intermedio"), y SHALL devolver un diccionario Python con la clave `explicacion` cuyo valor es una cadena de texto de no más de 200 palabras.
7. IF cualquier Tool lanza una excepción no controlada durante su ejecución, THEN la Tool SHALL capturarla internamente y devolver un diccionario con la clave `error` cuyo valor es una cadena de error en español sin stack trace, para que Max pueda comunicar el problema al Usuario de forma amigable.

---

### Requisito 12: Documentación del proyecto

**Historia de usuario:** Como evaluador de la hackatón y como futuro colaborador, quiero que el repositorio incluya documentación clara y completa en español, para que pueda entender, instalar y evaluar el proyecto sin asistencia adicional.

#### Criterios de aceptación

1. THE repositorio SHALL incluir un archivo `README.md` en español con las siguientes secciones en este orden: descripción del proyecto, para quién es, cómo funciona (resumen en no más de 150 palabras), prerrequisitos (Python 3.11+, cuenta AWS, dependencias), instrucciones de instalación numeradas paso a paso, instrucciones de uso para CLI y para Streamlit, diagrama de arquitectura en bloque de código Mermaid embebido, y sección de advertencias éticas.
2. THE repositorio SHALL incluir un archivo `LICENSE` que contenga el texto completo de la licencia MIT con el año 2025 y el nombre del titular del copyright.
3. THE repositorio SHALL incluir un archivo `requirements.txt` que liste todas las dependencias Python del proyecto con sus versiones fijas usando el operador `==`, sin rangos de versión ni dependencias sin versión.
4. THE repositorio SHALL incluir un archivo `ARCHITECTURE.md` con al menos un diagrama Mermaid en bloque de código fenced que represente el flujo completo: Usuario → CLI/Streamlit_UI → Max → Strands_SDK → Bedrock_Client → Tools → SQLite_DB, con etiquetas en español.
5. THE repositorio SHALL incluir un archivo `agentcore_config.md` con instrucciones numeradas paso a paso para desplegar Max en AgentCore, con una nota destacada al inicio que indique que el despliegue en AgentCore es opcional y que el sistema funciona localmente sin él.
6. THE repositorio SHALL incluir un archivo `docs/demo_script.md` con el guion completo de la demostración de 5 minutos estructurado en cinco secciones con tiempos estimados: (1) Presentación del problema (1 min), (2) Para quién es la solución (30 s), (3) Por qué importa (30 s), (4) Demo en vivo paso a paso (2 min 30 s), (5) Cierre (30 s).
7. THE `README.md` SHALL incluir una sección titulada "Ética y diseño responsable" que describa al menos las siguientes dos reglas de diseño: la regla de no enganche y la regla de derivación humana ante señales de riesgo.

---

### Requisito 13: Calidad de código y manejo de errores

**Historia de usuario:** Como desarrollador que revisará el código, quiero que el código esté comentado en español y maneje errores de forma clara, para que sea legible y mantenible sin esfuerzo adicional.

#### Criterios de aceptación

1. THE `agent/max_agent.py` y THE `agent/tools.py` SHALL incluir un docstring en español al inicio de cada función que describa en no más de 3 líneas: (1) qué hace la función, (2) qué parámetros recibe, y (3) qué devuelve o qué efecto secundario produce.
2. THE código SHALL usar bloques `try/except` específicos (capturando tipos de excepción concretos, no `Exception` genérica salvo como último recurso) para capturar errores en todas las llamadas al Bedrock_Client, operaciones de SQLite_DB e invocaciones de Tools, y SHALL devolver o mostrar mensajes de error en español que incluyan la acción que falló y una sugerencia de solución, sin imprimir el stack trace de Python al Usuario.
3. THE código SHALL implementar completamente todas las funciones definidas en `agent/tools.py` y `agent/max_agent.py`, sin cuerpos de función que contengan únicamente `pass`, la cadena `"TODO"`, o comentarios que indiquen implementación pendiente.
4. THE `db/setup.py` SHALL definir todas las tablas de SQLite_DB con claves primarias enteras autoincrementales, claves foráneas referenciando la tabla `usuarios`, restricciones NOT NULL en todos los campos obligatorios, y con `PRAGMA foreign_keys = ON` activado en la conexión.
5. WHEN el Bedrock_Client no responde en 30 segundos, THE código SHALL cancelar la operación pendiente usando el mecanismo de timeout del cliente de boto3, devolver al Usuario un mensaje en español indicando el problema de conectividad, y dejar el estado de la Sesión en SQLite_DB consistente (sin registros de mensaje parciales).
