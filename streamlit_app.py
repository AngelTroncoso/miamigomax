"""
Interfaz web de Mi Amigo Max construida con Streamlit.
Reutiliza directamente agent/max_agent.py y db/ sin reimplementar lógica.
Ejecutar con: streamlit run streamlit_app.py
"""

import logging
import os

from dotenv import load_dotenv

# Cargar variables de entorno al inicio
load_dotenv()

import streamlit as st

from db.setup import inicializar_db
from db import models as db_models
from agent.max_agent import create_agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Mi Amigo Max",
    page_icon="🌟",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Inicialización del estado de sesión
# ---------------------------------------------------------------------------
if "inicializado" not in st.session_state:
    st.session_state.inicializado = False
if "historial" not in st.session_state:
    st.session_state.historial = []  # list[dict{role, content}]
if "usuario_id" not in st.session_state:
    st.session_state.usuario_id = None
if "nombre_usuario" not in st.session_state:
    st.session_state.nombre_usuario = None
if "sesion_id" not in st.session_state:
    st.session_state.sesion_id = None
if "agent" not in st.session_state:
    st.session_state.agent = None

# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
st.title("🌟 Mi Amigo Max")
st.caption("Tu compañero de todos los días")
st.divider()

# ---------------------------------------------------------------------------
# Fase de configuración: solicitar nombre si aún no está inicializado
# ---------------------------------------------------------------------------
if not st.session_state.inicializado:
    st.subheader("¡Bienvenido/a!")
    st.write("Antes de comenzar, dime tu nombre para que pueda saludarte.")

    with st.form(key="form_nombre"):
        nombre_input = st.text_input(
            "Tu nombre:",
            placeholder="Escribe tu nombre aquí...",
            max_chars=50,
        )
        enviar = st.form_submit_button("Comenzar conversación")

    if enviar:
        nombre = nombre_input.strip()
        if not nombre or len(nombre) < 1:
            st.error("Por favor, escribe tu nombre (mínimo 1 carácter).")
        elif len(nombre) > 50:
            st.error("El nombre debe tener como máximo 50 caracteres.")
        else:
            # Verificar variables de entorno
            faltantes = [
                v for v in ("AWS_REGION", "BEDROCK_MODEL_ID", "DB_PATH")
                if not os.environ.get(v)
            ]
            if faltantes:
                st.error(
                    "Faltan variables de entorno requeridas: "
                    + ", ".join(faltantes)
                    + ". Consulta el archivo .env.example."
                )
                st.stop()

            # Inicializar DB
            ruta_db = os.environ["DB_PATH"]
            try:
                inicializar_db(ruta_db)
            except Exception as e:
                st.error(
                    f"No se pudo inicializar la base de datos en '{ruta_db}': {e}"
                )
                st.stop()

            # Obtener o crear usuario
            try:
                usuario = db_models.obtener_usuario_por_nombre(nombre, ruta_db=ruta_db)
                if usuario is None:
                    uid = db_models.crear_usuario(nombre, ruta_db=ruta_db)
                    usuario = db_models.obtener_usuario_por_nombre(nombre, ruta_db=ruta_db)
            except Exception as e:
                st.error(f"Error al registrar el usuario: {e}")
                st.stop()

            # Crear instancia del agente
            try:
                agente = create_agent(
                    usuario["id"], nombre, canal="streamlit", ruta_db=ruta_db
                )
            except Exception as e:
                st.error(f"Error al inicializar el agente: {e}")
                st.stop()

            # Persistir en session_state
            st.session_state.usuario_id = usuario["id"]
            st.session_state.nombre_usuario = nombre
            st.session_state.sesion_id = agente.sesion_id
            st.session_state.agent = agente
            st.session_state.inicializado = True

            # Mensaje de bienvenida inicial
            if agente.es_primera_sesion():
                bienvenida = (
                    f"¡Hola, {nombre}! Soy Max, tu compañero de conversación. "
                    "Estoy aquí para acompañarte en el día a día, ayudarte con tus "
                    "hábitos y charlar sobre lo que necesites. No soy médico ni "
                    "reemplazo a las personas que te quieren, pero sí puedo estar "
                    "aquí cuando lo necesites."
                )
            else:
                bienvenida = f"¡Hola de nuevo, {nombre}! ¿Cómo estás hoy?"

            st.session_state.historial.append(
                {"role": "assistant", "content": bienvenida}
            )
            st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Fase de conversación: mostrar historial y aceptar input
# ---------------------------------------------------------------------------

# Renderizar historial
for mensaje in st.session_state.historial:
    with st.chat_message(mensaje["role"]):
        st.write(mensaje["content"])

# Input del usuario
prompt_usuario = st.chat_input("Escribe tu mensaje aquí...")

if prompt_usuario:
    nombre = st.session_state.nombre_usuario

    # Mostrar mensaje del usuario de inmediato
    st.session_state.historial.append(
        {"role": "user", "content": prompt_usuario}
    )
    with st.chat_message("user"):
        st.write(prompt_usuario)

    # Generar respuesta con spinner
    with st.chat_message("assistant"):
        with st.spinner("Max está pensando..."):
            try:
                agente = st.session_state.agent
                respuesta = agente.chat(prompt_usuario)
            except Exception as e:  # noqa: BLE001
                logger.error("Error al invocar el agente en Streamlit: %s", e)
                respuesta = (
                    "En este momento tengo un problema de conexión. "
                    "Por favor, inténtalo de nuevo en unos momentos."
                )

        st.write(respuesta)

    st.session_state.historial.append(
        {"role": "assistant", "content": respuesta}
    )
