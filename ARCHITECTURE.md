# Arquitectura de Mi Amigo Max

Este documento describe la arquitectura técnica del sistema y los flujos de datos principales.

---

## Diagrama de componentes y flujo completo

```mermaid
flowchart TD
    U([Usuario]) -->|texto por consola| CLI["app.py — CLI\n(argparse, bucle input/print)"]
    U -->|texto en navegador| STR["streamlit_app.py — Streamlit UI\n(st.chat_input, st.chat_message)"]

    CLI -->|create_agent + chat| AGT
    STR -->|create_agent + chat| AGT

    subgraph AGT["agent/max_agent.py — MaxAgent"]
        direction TB
        SP["SYSTEM_PROMPT\n(constante inspeccionable)"]
        INIT["__init__: carga prompt,\ninstancia Strands Agent,\nregistra sesión en DB"]
        CHAT["chat(): detecta riesgo,\ngestiona pausa,\nprocesa turno,\nguarda mensajes en DB"]
        CLOSE["cerrar_sesion():\nactualiza timestamp_fin\ny duracion_minutos"]
        SP --> INIT --> CHAT --> CLOSE
    end

    CHAT -->|prompt + tools| SDK["Strands Agents SDK\n(orquestación de tools)"]
    SDK -->|invocar modelo| BED["Amazon Bedrock\nClaude 3.5 Sonnet"]
    BED -->|respuesta LLM| SDK
    SDK -->|texto final| CHAT

    SDK -->|tool call| TOOLS

    subgraph TOOLS["agent/tools.py — 5 Tools"]
        direction TB
        T1["registrar_habito\n(valida + persiste hábito)"]
        T2["obtener_resumen_habitos\n(calcula promedios por categoría)"]
        T3["detectar_senal_riesgo\n(análisis semántico con timeout 3s)"]
        T4["sugerir_pausa\n(pool 15 actividades, deduplicación)"]
        T5["explicar_tema\n(biblioteca local + niveles básico/intermedio)"]
    end

    T1 -->|INSERT habitos| DB
    T2 -->|SELECT habitos| DB
    T3 -->|SELECT mensajes\nINSERT flags_derivacion| DB
    T4 -->|SELECT sesiones| DB
    T5 -->|SELECT/UPDATE usuarios| DB

    subgraph DB["db/ — Persistencia SQLite local"]
        direction TB
        SETUP["db/setup.py\ninicializar_db(ruta_db)\nDDL en una sola transacción atómica"]
        MODELS["db/models.py\nfunciones CRUD\ncreate/read/update por entidad"]
        FILE[("Archivo .db\n(ruta en DB_PATH)")]
        SETUP --> FILE
        MODELS --> FILE
    end

    CLI -->|crear_sesion| DB
    STR -->|crear_sesion| DB
    CLOSE -->|cerrar_sesion| DB

    AGT -.->|despliegue opcional| ACS["AWS AgentCore\n(gestión en la nube)"]

    style AGT fill:#e8f4fd,stroke:#2196F3,color:#000
    style TOOLS fill:#fff8e1,stroke:#FF9800,color:#000
    style DB fill:#e8f5e9,stroke:#4CAF50,color:#000
    style ACS fill:#fce4ec,stroke:#E91E63,stroke-dasharray:5 5,color:#000
```

---

## Diagrama de tablas SQLite

```mermaid
erDiagram
    USUARIOS {
        int id PK
        text nombre UK
        text nivel_complejidad
        text fecha_registro
    }
    SESIONES {
        int id PK
        int usuario_id FK
        text canal
        text timestamp_inicio
        text timestamp_fin
        int duracion_minutos
    }
    MENSAJES {
        int id PK
        int usuario_id FK
        int sesion_id FK
        text rol
        text contenido
        text timestamp
    }
    HABITOS {
        int id PK
        int usuario_id FK
        text categoria
        real valor
        text unidad
        text timestamp
    }
    FLAGS_DERIVACION {
        int id PK
        int usuario_id FK
        int sesion_id FK
        text timestamp
        text nivel_riesgo
        text frases_detectadas
        text accion_tomada
    }

    USUARIOS ||--o{ SESIONES : "tiene"
    USUARIOS ||--o{ MENSAJES : "envía"
    USUARIOS ||--o{ HABITOS : "registra"
    USUARIOS ||--o{ FLAGS_DERIVACION : "genera"
    SESIONES ||--o{ MENSAJES : "contiene"
    SESIONES ||--o{ FLAGS_DERIVACION : "produce"
```

---

## Flujo de un turno de conversación

```mermaid
sequenceDiagram
    actor U as Usuario
    participant CLI as app.py
    participant MA as MaxAgent
    participant DSR as detectar_senal_riesgo
    participant SDK as Strands SDK
    participant BED as Amazon Bedrock
    participant DB as SQLite DB

    U->>CLI: escribe mensaje
    CLI->>MA: chat(mensaje)
    MA->>DB: guardar_mensaje(usuario, mensaje)
    MA->>DB: obtener_ultimos_n_mensajes(5)
    DB-->>MA: historial reciente
    MA->>DSR: detectar_senal_riesgo(msg, historial)
    DSR-->>MA: {nivel, frases_detectadas}
    alt nivel == "alto"
        MA->>DB: insertar_flag_derivacion(...)
    end
    MA->>SDK: prompt_turno + tools
    SDK->>BED: invocar modelo Claude
    BED-->>SDK: respuesta
    SDK-->>MA: texto de Max
    MA->>DB: guardar_mensaje(max, respuesta)
    MA-->>CLI: respuesta (str)
    CLI->>U: imprime "Max: ..."
```

---

## Decisiones de diseño

| Decisión | Alternativa considerada | Razón elegida |
|----------|------------------------|---------------|
| SQLite local | PostgreSQL / DynamoDB | Sin dependencias externas de BD; funciona offline |
| Decorator `@tool` de Strands SDK | Llamadas directas a Bedrock | El SDK gestiona el parsing de argumentos y el loop de herramientas |
| Timeout de 3s en `detectar_senal_riesgo` | Sin timeout | Fail-safe: ante error, asumir riesgo alto por seguridad |
| Sistema Prompt como constante en `max_agent.py` | Archivo `.txt` externo | Inspeccionable sin importar dependencias; siempre en sync con el código |
| Importación defensiva de Strands SDK | Requerir el SDK obligatoriamente | Permite ejecutar pruebas unitarias sin instalar el SDK completo |
