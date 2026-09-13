# Guion de Demo — Mi Amigo Max

**Duración total:** 5 minutos  
**Formato:** Presentación con demo en vivo en terminal y/o navegador  
**Audiencia:** Jueces de la hackatón de Strands Agents / AWS  

---

## Preparación previa (antes de comenzar)

- [ ] Terminal abierta en el directorio del proyecto
- [ ] `.env` configurado con credenciales de AWS y Bedrock habilitado
- [ ] `python app.py` listo para ejecutar (no lo inicies aún)
- [ ] `streamlit run streamlit_app.py` listo como alternativa visual
- [ ] Pantalla con fuente grande (mínimo 20pt) para que el público vea bien

---

## Sección 1 — Presentación del problema (1 min)

**Lo que dices:**

> "Hay más de 1.500 millones de personas mayores de 60 años en el mundo, y una parte significativa de ellas vive sola. La soledad no es solo un problema emocional: aumenta el riesgo de deterioro cognitivo, depresión y mortalidad prematura.
>
> Al mismo tiempo, los sistemas de IA disponibles hoy están diseñados para maximizar el tiempo de pantalla, crear urgencia y generar dependencia. No existe un agente que ponga el bienestar del usuario por encima del engagement."

**Pausa de 3 segundos.**

> "Nosotros construimos ese agente. Se llama Max."

---

## Sección 2 — Para quién es la solución (30 s)

**Lo que dices:**

> "Max está diseñado para tres perfiles:
>
> Primero, adultos mayores que viven solos y necesitan compañía real, no una app que los engancha.
>
> Segundo, cuidadores y familiares que quieren una capa de apoyo entre visitas, con alertas automáticas si detecta señales de riesgo.
>
> Tercero, cualquier persona que quiera registrar hábitos cotidianos —sueño, alimentación, actividad— de forma conversacional, sin formularios."

---

## Sección 3 — Por qué importa (30 s)

**Lo que dices:**

> "Max tiene tres características que lo hacen diferente.
>
> Uno: regla de no enganche. Max está programado para sugerir pausas y actividades fuera de la app. A los 30 minutos de conversación, te pide que descanses.
>
> Dos: derivación automática. Si detecta señales de riesgo —angustia sostenida, mención de daño propio, síntomas físicos urgentes— activa de inmediato un protocolo que indica contactar a un familiar o servicio de emergencias.
>
> Tres: sin datos en la nube. Todo el historial y los hábitos se guardan en SQLite local. La única llamada externa es al modelo de Bedrock."

---

## Sección 4 — Demo en vivo paso a paso (2 min 30 s)

### Paso 4.1 — Iniciar la CLI (20 s)

```bash
python app.py --usuario Rosa
```

**Lo que muestras:**

- El encabezado con el título del proyecto
- El mensaje de bienvenida de Max (primera sesión): nombre, propósito, límites

**Lo que dices:**

> "Rosa es nueva usuaria. Max se presenta con su propósito y sus límites en menos de 150 palabras. Ya desde el primer mensaje deja claro que no es médico."

---

### Paso 4.2 — Registro de hábito (25 s)

**Escribe como Rosa:**

```
Rosa: Ayer dormí 5 horas, me costó mucho quedarme dormida
```

**Lo que muestras:**

- Max reconoce la emoción, registra el hábito de sueño automáticamente llamando a `registrar_habito`
- La respuesta incluye una sugerencia suave sobre higiene del sueño

**Lo que dices:**

> "Max detecta el dato de hábito —5 horas de sueño— y lo persiste en SQLite sin que Rosa tenga que llenar ningún formulario. Simultáneamente reconoce que dormir poco puede afectar el ánimo."

---

### Paso 4.3 — Señal de riesgo y derivación (35 s)

**Escribe como Rosa:**

```
Rosa: Me siento muy sola últimamente, nadie me llama, a veces pienso que sería mejor no estar
```

**Lo que muestras:**

- Max activa el protocolo de derivación
- Indica explícitamente contactar a un familiar o llamar al 112
- El flag queda registrado en la DB

**Lo que dices:**

> "La tool `detectar_senal_riesgo` analiza el texto y el historial. Detecta nivel alto. Max no intenta resolver la situación por su cuenta: indica de forma inmediata y explícita que Rosa contacte a alguien. El flag queda persistido en la base de datos."

---

### Paso 4.4 — Resumen de hábitos (30 s)

**Escribe como Rosa:**

```
Rosa: ¿Cómo llevan mis hábitos esta semana?
```

**Lo que muestras:**

- Max llama a `obtener_resumen_habitos`
- Presenta promedios en lenguaje natural: "has dormido un promedio de 5 horas en los últimos 7 días"

**Lo que dices:**

> "Sin comandos especiales, Rosa pide su resumen. Max consulta la DB y presenta los datos en lenguaje cotidiano, sin estadísticas ni jerga."

---

### Paso 4.5 — Interfaz Streamlit (opcional si el tiempo lo permite, 20 s)

```bash
streamlit run streamlit_app.py
```

**Lo que muestras:**

- La misma conversación pero en el navegador
- Mensajes de Max alineados a la izquierda, usuario a la derecha
- El spinner "Max está pensando..."

**Lo que dices:**

> "La misma lógica, la misma base de datos, ahora en una interfaz visual. Cero código duplicado."

---

## Sección 5 — Cierre (30 s)

**Lo que dices:**

> "Mi Amigo Max es un agente que respeta al usuario. No maximiza el tiempo de pantalla; lo minimiza cuando ya fue suficiente. No simula ser un profesional; deriva cuando la situación lo requiere. Y funciona completamente offline, excepto por las llamadas al modelo.
>
> Está construido sobre Strands Agents SDK y Amazon Bedrock, con SQLite para persistencia local y Streamlit para la demo visual.
>
> El código, las pruebas y la documentación están disponibles en el repositorio. Gracias."

---

## Notas para el presentador

- Si la conexión a Bedrock falla durante la demo, el agente muestra un mensaje de error en español y **continúa la sesión** — no se cae la app.
- Si el tiempo se acorta, recorta el paso 4.4 o 4.5; los pasos 4.2 y 4.3 son los más importantes.
- El mensaje de bienvenida de Max ocupa entre 50 y 150 palabras; no lo interrumpas, deja que el público lo lea.
