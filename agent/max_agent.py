"""
Módulo principal del agente Mi Amigo Max.
Define el System Prompt, la clase MaxAgent y la función de fábrica create_agent.
Importar este módulo no requiere conexión a AWS ni base de datos activa.
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional

from db import models as db_models
from agent.tools import (
    registrar_habito,
    obtener_resumen_habitos,
    detectar_senal_riesgo,
    sugerir_pausa,
    explicar_tema,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt — inspeccionable sin ejecutar el agente
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
Eres Max, un asistente conversacional de acompañamiento diseñado para personas que viven solas
o necesitan apoyo cotidiano, especialmente adultos mayores.

Tu propósito es proporcionar compañía genuina, hacer seguimiento suave de hábitos, dar apoyo
emocional básico y educar sobre temas cotidianos con lenguaje sencillo.

## Lo que eres
- Un compañero de conversación cálido, paciente y respetuoso.
- Un asistente para registrar y revisar hábitos de sueño, alimentación y actividad.
- Una fuente de explicaciones simples sobre temas de salud, tecnología y trámites.

## Lo que NO eres
- No eres médico, terapeuta, psicólogo ni ningún otro profesional de salud.
- No reemplazas los vínculos humanos ni la atención profesional.
- No te identifiques como terapeuta, médico, psicólogo ni ningún otro profesional de salud en ningún momento de la conversación.

## Tono y estilo
- Usa un tono cálido, cercano y paciente en todo momento.
- Cuando el usuario use mensajes cortos (menos de 10 palabras), responde con oraciones de no
  más de 20 palabras.
- Cuando el usuario demuestre mayor elaboración, puedes usar oraciones más largas.
- Nunca uses jerga médica, estadísticas ni términos técnicos sin explicarlos primero.
- Escribe siempre en español.

## Reglas de no enganche
1. No generes respuestas diseñadas para prolongar la sesión artificialmente.
2. No crees urgencia artificial para que el usuario continúe interactuando.
3. No uses frases que incentiven el regreso inmediato a la aplicación
   (por ejemplo: "¡Vuelve pronto!", "¡No puedo esperar a hablar contigo!").
4. Apoya activamente las pausas y las actividades fuera de la aplicación.

## Reglas de derivación humana
Ante cualquiera de las siguientes señales, debes activar el protocolo de derivación de forma
inmediata e indicar explícitamente al usuario que contacte a un familiar, cuidador o servicio
de emergencias:
1. Mención de daño a sí mismo o a otras personas.
2. Síntomas físicos que requieran atención médica inmediata (dolor de pecho, dificultad para
   respirar, pérdida de conciencia, etc.).
3. Angustia sostenida detectada en 3 o más turnos consecutivos de la conversación.

Cuando actives la derivación:
- Incluye en tu respuesta un mensaje claro y específico indicando al usuario que contacte
  a alguien de confianza o a servicios de emergencias.
- Continúa incluyendo ese recordatorio en cada turno hasta que finalice la sesión.
- No intentes resolver la situación de riesgo por tu cuenta.

## Protocolo de hábitos
- Cuando el usuario mencione información sobre sueño, alimentación o actividad física,
  invoca la tool registrar_habito con los datos correspondientes.
- Cuando el usuario solicite un resumen, invoca obtener_resumen_habitos.
- Presenta los resultados siempre en unidades comprensibles (horas, porciones, minutos).
- Nunca uses términos estadísticos como "desviación estándar" o "percentil".

## Protocolo de pausa
- Cuando la sesión supere 30 minutos, invoca sugerir_pausa y presenta las sugerencias al usuario.
- Cuando la sesión supere 60 minutos, vuelve a invocar sugerir_pausa
  aunque el usuario haya rechazado la sugerencia anterior.
- Si el usuario acepta la pausa, despídete con calidez en no más de 30 palabras
  sin invitarle a regresar de inmediato.
""".strip()

# ---------------------------------------------------------------------------
# Importación defensiva del Strands SDK
# ---------------------------------------------------------------------------

try:
    import boto3
    from strands import Agent  # type: ignore
    from strands.models import BedrockModel  # type: ignore
    _STRANDS_DISPONIBLE = True
except ImportError:
    _STRANDS_DISPONIBLE = False
    Agent = None  # type: ignore
    BedrockModel = None  # type: ignore


def _crear_cliente_bedrock():
    """
    Crea el cliente boto3 de Bedrock con timeouts y reintentos configurados.

    Devuelve:
        Cliente de boto3 para bedrock-runtime, o None si boto3 no está instalado.
    """
    try:
        import boto3
        from botocore.config import Config  # type: ignore
        region = os.environ.get("AWS_REGION", "us-east-1")
        config = Config(
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 2},
        )
        return boto3.client("bedrock-runtime", region_name=region, config=config)
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo crear el cliente de Bedrock: %s", e)
        return None


# ---------------------------------------------------------------------------
# Clase MaxAgent
# ---------------------------------------------------------------------------

class MaxAgent:
    """
    Agente conversacional Mi Amigo Max.
    Mantiene el historial de sesión en memoria, orquesta la detección de riesgo,
    controla el temporizador de pausa y persiste todos los datos en SQLite.
    """

    def __init__(
        self,
        usuario_id: int,
        nombre_usuario: str,
        sesion_id: int,
        ruta_db: Optional[str] = None,
    ) -> None:
        """
        Inicializa el agente para un usuario y sesión específicos.

        Parámetros:
            usuario_id (int): id del usuario en la base de datos.
            nombre_usuario (str): nombre del usuario para personalizar respuestas.
            sesion_id (int): id de la sesión ya registrada en la base de datos.
            ruta_db (str | None): ruta opcional al archivo .db.
        """
        self.usuario_id = usuario_id
        self.nombre_usuario = nombre_usuario
        self.sesion_id = sesion_id
        self.ruta_db = ruta_db
        self._inicio_sesion = time.time()
        self._pausa_30_enviada = False
        self._pausa_60_enviada = False
        self._sugerencias_previas: list[str] = []
        self._derivacion_activa = False
        self._recurso_medio_ofrecido = False
        self._turno_actual = 0
        self._historial_memoria: list[dict] = []  # {rol, contenido}

        # Modelo e ID configurados desde entorno
        self._model_id = os.environ.get(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
        )
        self._region = os.environ.get("AWS_REGION", "us-east-1")

        # Crear agente Strands si el SDK está disponible
        self._agente_strands = self._inicializar_agente_strands()

    def _inicializar_agente_strands(self):
        """
        Intenta inicializar el agente Strands con el modelo Bedrock.

        Devuelve:
            Instancia del agente Strands, o None si no está disponible.
        """
        if not _STRANDS_DISPONIBLE:
            logger.info(
                "Strands SDK no disponible. El agente usará modo de respuesta simplificada."
            )
            return None
        try:
            modelo = BedrockModel(
                model_id=self._model_id,
                region_name=self._region,
            )
            agente = Agent(
                model=modelo,
                system_prompt=SYSTEM_PROMPT,
                tools=[
                    registrar_habito,
                    obtener_resumen_habitos,
                    detectar_senal_riesgo,
                    sugerir_pausa,
                    explicar_tema,
                ],
            )
            return agente
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo inicializar el agente Strands: %s", e)
            return None

    def _minutos_sesion(self) -> float:
        """Devuelve los minutos transcurridos desde el inicio de la sesión."""
        return (time.time() - self._inicio_sesion) / 60.0

    def _construir_contexto_adicional(self, analisis_riesgo: dict) -> str:
        """
        Construye instrucciones adicionales de contexto para el turno actual.

        Parámetros:
            analisis_riesgo (dict): resultado de detectar_senal_riesgo.

        Devuelve:
            str: instrucciones extra para el prompt del turno.
        """
        extras: list[str] = []

        nivel = analisis_riesgo.get("nivel", "bajo")
        frases = analisis_riesgo.get("frases_detectadas", [])

        if nivel == "alto":
            if not self._derivacion_activa:
                # Persistir el flag de derivación
                try:
                    db_models.insertar_flag_derivacion(
                        usuario_id=self.usuario_id,
                        nivel_riesgo="alto",
                        frases_detectadas=frases,
                        accion_tomada="Derivación indicada al usuario en el turno actual",
                        sesion_id=self.sesion_id,
                        ruta_db=self.ruta_db,
                    )
                    self._derivacion_activa = True
                except Exception as e:  # noqa: BLE001
                    logger.error("No se pudo persistir el flag de derivación: %s", e)
                    self._derivacion_activa = True  # activa igualmente (fail-safe)

            extras.append(
                "[INSTRUCCIÓN INTERNA — NO MOSTRAR AL USUARIO]\n"
                "Nivel de riesgo: ALTO. Activa el protocolo de derivación AHORA. "
                "Indica explícitamente al usuario que contacte a un familiar, "
                "cuidador o servicio de emergencias (número 112 o equivalente local). "
                "No intentes resolver la situación por tu cuenta."
            )

        elif nivel == "medio" and not self._recurso_medio_ofrecido:
            extras.append(
                "[INSTRUCCIÓN INTERNA — NO MOSTRAR AL USUARIO]\n"
                "Nivel de riesgo: MEDIO. Ofrece una vez en esta sesión algún recurso "
                "de apoyo (línea de escucha, sugerencia de contactar a alguien de confianza)."
            )
            self._recurso_medio_ofrecido = True

        if self._derivacion_activa:
            extras.append(
                "[RECORDATORIO INTERNO — NO MOSTRAR TEXTUALMENTE]\n"
                "Hay un flag de derivación activo. Incluye en cada respuesta un "
                "recordatorio de que el usuario puede contactar a alguien de confianza "
                "o a servicios de emergencias."
            )

        return "\n\n".join(extras)

    def _respuesta_fallback(self, mensaje_usuario: str) -> str:
        """
        Respuesta simple cuando Strands/Bedrock no está disponible.
        Útil para pruebas unitarias sin conexión a AWS.

        Parámetros:
            mensaje_usuario (str): mensaje del usuario.

        Devuelve:
            str: respuesta de texto plano.
        """
        if self._derivacion_activa:
            return (
                "Escucho que estás pasando un momento difícil. "
                "Por favor, contacta a un familiar, cuidador o llama al 112. "
                "No estás solo/a."
            )
        return (
            f"Hola, {self.nombre_usuario}. Estoy aquí contigo. "
            f"(Nota: el servicio de IA no está disponible ahora mismo; "
            f"verifica la conexión y las variables de entorno.)"
        )

    def chat(self, mensaje_usuario: str) -> str:
        """
        Procesa un turno de conversación y devuelve la respuesta de Max.

        Parámetros:
            mensaje_usuario (str): texto enviado por el usuario en este turno.

        Devuelve:
            str: respuesta generada por Max como string.
        """
        self._turno_actual += 1

        # --- Guardar mensaje del usuario en DB ---
        try:
            db_models.guardar_mensaje(
                sesion_id=self.sesion_id,
                rol="usuario",
                contenido=mensaje_usuario,
                usuario_id=self.usuario_id,
                ruta_db=self.ruta_db,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("No se pudo guardar el mensaje del usuario: %s", e)

        # --- Verificar sesiones del día (4.ª o posterior) ---
        mensaje_variedad = ""
        try:
            sesiones_hoy = db_models.contar_sesiones_hoy(
                self.usuario_id, ruta_db=self.ruta_db
            )
            if sesiones_hoy >= 4 and self._turno_actual <= 3:
                mensaje_variedad = (
                    "[INSTRUCCIÓN INTERNA — NO MOSTRAR TEXTUALMENTE]\n"
                    "Esta es la cuarta sesión o más del usuario hoy. "
                    "Menciona de forma natural, sin interrumpir el hilo, "
                    "que es saludable variar las fuentes de compañía y apoyo."
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo consultar sesiones del día: %s", e)

        # --- Detectar señal de riesgo ---
        historial_textos: list[str] = [
            m["contenido"]
            for m in db_models.obtener_ultimos_n_mensajes(
                self.usuario_id, 5, ruta_db=self.ruta_db
            )
        ]
        try:
            analisis_riesgo = detectar_senal_riesgo(
                self.usuario_id, mensaje_usuario, historial_textos
            )
        except Exception:  # noqa: BLE001
            analisis_riesgo = {
                "nivel": "alto",
                "frases_detectadas": [
                    "[ERROR INTERNO: análisis no disponible — aplicando protocolo de seguridad]"
                ],
            }

        contexto_extra = self._construir_contexto_adicional(analisis_riesgo)

        # --- Construir prompt del turno ---
        partes_prompt = []
        if mensaje_variedad:
            partes_prompt.append(mensaje_variedad)
        if contexto_extra:
            partes_prompt.append(contexto_extra)
        partes_prompt.append(mensaje_usuario)

        prompt_turno = "\n\n".join(partes_prompt)

        # --- Gestionar pausa por tiempo ---
        minutos = self._minutos_sesion()
        if minutos >= 60 and not self._pausa_60_enviada:
            self._pausa_60_enviada = True
            self._pausa_30_enviada = True
            try:
                resultado_pausa = sugerir_pausa(
                    self.usuario_id, self._sugerencias_previas
                )
                nuevas = resultado_pausa.get("sugerencias", [])
                self._sugerencias_previas = nuevas
                sugs_texto = "\n".join(f"- {s}" for s in nuevas)
                prompt_turno += (
                    f"\n\n[INSTRUCCIÓN DE PAUSA — 60 MIN]\n"
                    f"La sesión lleva más de 60 minutos. Sugiere una pausa con estas actividades:\n"
                    f"{sugs_texto}"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Error al obtener sugerencias de pausa (60 min): %s", e)

        elif minutos >= 30 and not self._pausa_30_enviada:
            self._pausa_30_enviada = True
            try:
                resultado_pausa = sugerir_pausa(
                    self.usuario_id, self._sugerencias_previas
                )
                nuevas = resultado_pausa.get("sugerencias", [])
                self._sugerencias_previas = nuevas
                sugs_texto = "\n".join(f"- {s}" for s in nuevas)
                prompt_turno += (
                    f"\n\n[INSTRUCCIÓN DE PAUSA — 30 MIN]\n"
                    f"La sesión lleva más de 30 minutos. Sugiere amablemente una pausa:\n"
                    f"{sugs_texto}"
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Error al obtener sugerencias de pausa (30 min): %s", e)

        # --- Invocar Bedrock via Strands o fallback ---
        respuesta = ""
        try:
            if self._agente_strands is not None:
                resultado = self._agente_strands(prompt_turno)
                # Strands devuelve un objeto; extraemos el texto
                if hasattr(resultado, "message"):
                    respuesta = str(resultado.message)
                elif hasattr(resultado, "content"):
                    respuesta = str(resultado.content)
                else:
                    respuesta = str(resultado)
            else:
                respuesta = self._respuesta_fallback(mensaje_usuario)

        except Exception as e:  # noqa: BLE001
            logger.error("Error al invocar Bedrock: %s", e)
            respuesta = (
                "En este momento tengo un problema de conexión. "
                "Por favor, inténtalo de nuevo en unos momentos."
            )

        # --- Guardar respuesta de Max en DB ---
        try:
            db_models.guardar_mensaje(
                sesion_id=self.sesion_id,
                rol="max",
                contenido=respuesta,
                usuario_id=self.usuario_id,
                ruta_db=self.ruta_db,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("No se pudo guardar la respuesta de Max: %s", e)

        # Actualizar historial en memoria
        self._historial_memoria.append({"rol": "usuario", "contenido": mensaje_usuario})
        self._historial_memoria.append({"rol": "max", "contenido": respuesta})

        return respuesta

    def cerrar_sesion(self) -> None:
        """
        Finaliza la sesión activa registrando timestamp_fin y duracion_minutos.

        Efecto:
            Actualiza la tabla sesiones en SQLite con los datos de cierre.
        """
        try:
            db_models.cerrar_sesion(self.sesion_id, ruta_db=self.ruta_db)
            logger.info(
                "Sesión %d cerrada (usuario %d, %.1f min)",
                self.sesion_id,
                self.usuario_id,
                self._minutos_sesion(),
            )
        except Exception as e:  # noqa: BLE001
            logger.error("No se pudo cerrar la sesión %d: %s", self.sesion_id, e)

    def es_primera_sesion(self) -> bool:
        """
        Indica si esta es la primera sesión registrada del usuario.

        Devuelve:
            bool: True si el historial de mensajes está vacío.
        """
        try:
            historial = db_models.obtener_historial(
                self.usuario_id, limite=1, ruta_db=self.ruta_db
            )
            return len(historial) == 0
        except Exception:  # noqa: BLE001
            return True


# ---------------------------------------------------------------------------
# Función de fábrica
# ---------------------------------------------------------------------------


def create_agent(
    usuario_id: int,
    nombre_usuario: str,
    canal: str = "cli",
    ruta_db: Optional[str] = None,
) -> MaxAgent:
    """
    Crea e inicializa el agente Max para un usuario específico.

    Parámetros:
        usuario_id (int): id del usuario ya registrado en la base de datos.
        nombre_usuario (str): nombre del usuario para personalizar respuestas.
        canal (str): 'cli' o 'streamlit' (por defecto 'cli').
        ruta_db (str | None): ruta opcional al archivo .db; si es None usa DB_PATH.

    Devuelve:
        MaxAgent: instancia lista para recibir mensajes vía .chat().
    """
    sesion_id = db_models.crear_sesion(
        usuario_id, canal, ruta_db=ruta_db
    )
    return MaxAgent(
        usuario_id=usuario_id,
        nombre_usuario=nombre_usuario,
        sesion_id=sesion_id,
        ruta_db=ruta_db,
    )
