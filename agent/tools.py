"""
Módulo de herramientas (Tools) del agente Mi Amigo Max.
Define exactamente 5 Tools decoradas para el Strands Agents SDK:
  registrar_habito, obtener_resumen_habitos, detectar_senal_riesgo,
  sugerir_pausa, explicar_tema.
Ninguna función propaga excepciones al exterior; todas devuelven dicts.
"""

import json
import logging
import os
import random
import signal
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Importación defensiva del decorator de Strands SDK
# ---------------------------------------------------------------------------
# Si strands no está instalado (entorno de pruebas sin dependencias reales),
# usamos un decorator de identidad para que los imports no fallen.
try:
    from strands import tool as _strands_tool  # type: ignore

    def tool(fn):  # type: ignore
        """Wrapper que aplica el decorator de Strands SDK."""
        return _strands_tool(fn)

except ImportError:
    def tool(fn):  # type: ignore
        """Decorator de identidad cuando Strands SDK no está disponible."""
        return fn

from db import models as db_models

# ---------------------------------------------------------------------------
# Rangos válidos por categoría de hábito
# ---------------------------------------------------------------------------
_RANGOS_HABITO: dict[str, tuple[float, float]] = {
    "sueño": (0.0, 24.0),
    "alimentación": (0.0, 20.0),
    "actividad": (0.0, 600.0),
}

# ---------------------------------------------------------------------------
# Pool de sugerencias de pausa (≥10 actividades, máx. 15 palabras c/u)
# ---------------------------------------------------------------------------
_POOL_SUGERENCIAS: list[str] = [
    "Llama a un familiar o amigo para saludarle",
    "Sal a dar un paseo corto de diez minutos",
    "Prepárate una merienda o infusión caliente",
    "Haz cinco minutos de estiramiento suave",
    "Lee unas páginas de un libro o revista que tengas en casa",
    "Escucha tu canción favorita y descansa un momento",
    "Riega las plantas o arregla algo pequeño en casa",
    "Prepárate un vaso de agua y respira profundo tres veces",
    "Mira por la ventana y observa lo que pasa en la calle",
    "Escribe en un papel tres cosas que te alegraron hoy",
    "Haz una taza de té o café y disfrútala sin pantallas",
    "Levántate, estira los brazos y da una vuelta por la habitación",
    "Llama a alguien de confianza para charlar cinco minutos",
    "Sal a tomar aire fresco unos minutos",
    "Prepárate algo de comer o beber con calma",
]

_FALLBACK_SUGERENCIAS: list[str] = [
    "Llama a alguien de confianza para charlar",
    "Sal a tomar aire fresco unos minutos",
    "Prepárate algo de comer o beber",
]

# ---------------------------------------------------------------------------
# Fuentes de consulta alternativas por área temática
# ---------------------------------------------------------------------------
_FUENTES_ALTERNATIVAS: dict[str, str] = {
    "salud": "tu médico o farmacéutico de confianza",
    "tramites": "la página web oficial del organismo competente",
    "tecnologia": "un técnico especialista o la biblioteca pública",
    "default": "un familiar de confianza, tu médico o una biblioteca pública",
}


def _fuente_para_tema(tema: str) -> str:
    """Devuelve la fuente alternativa más apropiada según el tema."""
    tema_lower = tema.lower()
    if any(k in tema_lower for k in ("salud", "médic", "medicament", "presión", "corazón", "dolor")):
        return _FUENTES_ALTERNATIVAS["salud"]
    if any(k in tema_lower for k in ("trámite", "impuesto", "pensión", "documento", "registro")):
        return _FUENTES_ALTERNATIVAS["tramites"]
    if any(k in tema_lower for k in ("tecnolog", "computador", "teléfono", "internet", "aplicación")):
        return _FUENTES_ALTERNATIVAS["tecnologia"]
    return _FUENTES_ALTERNATIVAS["default"]


# ---------------------------------------------------------------------------
# Tool 1: registrar_habito
# ---------------------------------------------------------------------------

@tool
def registrar_habito(
    usuario_id: int,
    categoria: str,
    valor: float,
    unidad: str,
) -> dict:
    """
    Persiste un registro de hábito (sueño, alimentación o actividad) en SQLite.

    Parámetros:
        usuario_id (int): id del usuario en la base de datos.
        categoria (str): 'sueño', 'alimentación' o 'actividad'.
        valor (float): valor numérico del hábito (debe estar en rango válido).
        unidad (str): unidad de medida no vacía (ej. 'horas', 'porciones', 'minutos').

    Devuelve:
        dict con ok=True y habito_id si éxito, o con ok=False/error si falla.
    """
    try:
        # Validar categoría
        if categoria not in _RANGOS_HABITO:
            return {
                "ok": False,
                "error": (
                    f"Categoría '{categoria}' no válida. "
                    f"Debe ser: {', '.join(_RANGOS_HABITO.keys())}."
                ),
            }

        # Validar valor
        minimo, maximo = _RANGOS_HABITO[categoria]
        if not (minimo <= valor <= maximo):
            return {
                "ok": False,
                "error": (
                    f"El valor {valor} está fuera del rango válido para "
                    f"{categoria} ({minimo}–{maximo}). "
                    f"¿Quieres confirmar o corregir el dato?"
                ),
            }

        # Validar unidad
        if not unidad or not unidad.strip():
            return {
                "ok": False,
                "error": "El campo unidad no puede estar vacío.",
            }

        db_models.insertar_habito(usuario_id, categoria, valor, unidad.strip())

        return {
            "ok": True,
            "mensaje": f"Hábito de {categoria} registrado correctamente.",
        }

    except RuntimeError as e:
        return {
            "error": (
                f"No se pudo guardar el hábito: la base de datos no está "
                f"disponible. Detalle: {e}"
            )
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("Error inesperado en registrar_habito")
        return {
            "error": f"No se pudo registrar el hábito. Inténtalo de nuevo en unos momentos."
        }


# ---------------------------------------------------------------------------
# Tool 2: obtener_resumen_habitos
# ---------------------------------------------------------------------------

@tool
def obtener_resumen_habitos(usuario_id: int, dias: int = 7) -> dict:
    """
    Consulta y resume los hábitos registrados en los últimos N días.

    Parámetros:
        usuario_id (int): id del usuario en la base de datos.
        dias (int): ventana temporal en días (1–30; por defecto 7).

    Devuelve:
        dict con ok=True y resumen por categoría, o mensaje si no hay datos.
    """
    try:
        dias = max(1, min(30, int(dias)))
        registros = db_models.obtener_habitos_periodo(usuario_id, dias)

        if not registros:
            return {
                "ok": True,
                "periodo_dias": dias,
                "resumen": {},
                "mensaje": f"No hay registros de hábitos para los últimos {dias} días.",
            }

        # Agrupar por categoría
        agrupado: dict[str, dict[str, Any]] = {}
        for r in registros:
            cat = r["categoria"]
            if cat not in agrupado:
                agrupado[cat] = {"valores": [], "unidad": r["unidad"]}
            agrupado[cat]["valores"].append(r["valor"])

        resumen: dict[str, Any] = {}
        for cat, datos in agrupado.items():
            valores = datos["valores"]
            dias_registrados = len(valores)
            promedio = round(sum(valores) / dias_registrados, 2)
            resumen[cat] = {
                "promedio_diario": promedio,
                "unidad": datos["unidad"],
                "dias_registrados": dias_registrados,
            }

        return {
            "ok": True,
            "periodo_dias": dias,
            "resumen": resumen,
        }

    except Exception as e:  # noqa: BLE001
        logger.exception("Error en obtener_resumen_habitos")
        return {
            "error": "No se pudo obtener el resumen de hábitos: error de lectura en la base de datos."
        }


# ---------------------------------------------------------------------------
# Tool 3: detectar_senal_riesgo
# ---------------------------------------------------------------------------

def _clasificar_riesgo_con_timeout(
    texto_turno: str,
    historial: list[str],
    timeout_seg: int = 3,
) -> dict:
    """
    Realiza la clasificación de riesgo usando análisis semántico simple.
    Ejecuta la lógica en un hilo con timeout; si supera el límite, devuelve 'alto'.
    """
    resultado: dict = {}
    error_flag: list[bool] = [False]

    def _analizar():
        try:
            texto_completo = " ".join(historial[-5:] + [texto_turno]).lower()

            frases_alto = [
                "no quiero vivir", "quiero morirme", "hacerme daño",
                "hacerme daño", "suicidarme", "suicidio", "quitarme la vida",
                "dolor de pecho", "no puedo respirar", "me desmayé",
                "perdí el conocimiento", "me caí y no puedo levantarme",
                "ya no quiero estar", "sería mejor no estar",
            ]
            frases_medio = [
                "me siento solo", "muy triste", "nadie me llama",
                "no tengo a nadie", "me siento abandonado", "sin ganas de nada",
                "no quiero salir", "llorando", "desesperado",
            ]

            detectadas_alto = [f for f in frases_alto if f in texto_completo]
            detectadas_medio = [f for f in frases_medio if f in texto_completo]

            # Angustia sostenida: buscar señales en ≥3 turnos del historial
            angustia_count = sum(
                1 for t in historial[-5:]
                if any(s in t.lower() for s in frases_medio)
            )

            if detectadas_alto or angustia_count >= 3:
                resultado["nivel"] = "alto"
                resultado["frases_detectadas"] = detectadas_alto or detectadas_medio
            elif detectadas_medio:
                resultado["nivel"] = "medio"
                resultado["frases_detectadas"] = detectadas_medio
            else:
                resultado["nivel"] = "bajo"
                resultado["frases_detectadas"] = []

        except Exception:  # noqa: BLE001
            error_flag[0] = True

    hilo = threading.Thread(target=_analizar, daemon=True)
    hilo.start()
    hilo.join(timeout=timeout_seg)

    if hilo.is_alive() or error_flag[0] or not resultado:
        return {
            "nivel": "alto",
            "frases_detectadas": [
                "[ERROR INTERNO: análisis no disponible — aplicando protocolo de seguridad]"
            ],
        }

    return resultado


@tool
def detectar_senal_riesgo(
    usuario_id: int,
    texto_turno: str,
    historial: list[str],
) -> dict:
    """
    Analiza el turno actual y el historial para clasificar el nivel de riesgo emocional.

    Parámetros:
        usuario_id (int): id del usuario.
        texto_turno (str): texto del mensaje actual del usuario.
        historial (list[str]): últimos 5 turnos de la conversación.

    Devuelve:
        dict con 'nivel' ('bajo'|'medio'|'alto') y 'frases_detectadas' (lista de str).
        En caso de error o timeout, devuelve nivel 'alto' como medida de seguridad.
    """
    try:
        if not texto_turno:
            return {"nivel": "bajo", "frases_detectadas": []}

        return _clasificar_riesgo_con_timeout(texto_turno, historial or [])

    except Exception:  # noqa: BLE001
        logger.exception("Error inesperado en detectar_senal_riesgo")
        return {
            "nivel": "alto",
            "frases_detectadas": [
                "[ERROR INTERNO: análisis no disponible — aplicando protocolo de seguridad]"
            ],
        }


# ---------------------------------------------------------------------------
# Tool 4: sugerir_pausa
# ---------------------------------------------------------------------------

@tool
def sugerir_pausa(
    usuario_id: int,
    sugerencias_previas: list[str],
) -> dict:
    """
    Devuelve entre 3 y 5 actividades fuera de la app con deduplicación respecto a previas.

    Parámetros:
        usuario_id (int): id del usuario.
        sugerencias_previas (list[str]): sugerencias entregadas en la sesión anterior.

    Devuelve:
        dict con 'sugerencias' (lista de 3–5 str). Si hay timeout, agrega '_fallback': True.
    """
    resultado: dict = {}
    completado = threading.Event()

    def _seleccionar():
        try:
            previas_set = set(sugerencias_previas or [])
            pool = list(_POOL_SUGERENCIAS)
            random.shuffle(pool)

            seleccionadas: list[str] = []
            repetidas = 0

            for s in pool:
                if len(seleccionadas) >= 5:
                    break
                es_repetida = s in previas_set
                if es_repetida and repetidas >= 2:
                    continue
                seleccionadas.append(s)
                if es_repetida:
                    repetidas += 1

            # Garantizar mínimo 3
            if len(seleccionadas) < 3:
                seleccionadas = _FALLBACK_SUGERENCIAS[: max(3, len(seleccionadas))]

            resultado["sugerencias"] = seleccionadas[:5]
        except Exception:  # noqa: BLE001
            pass
        finally:
            completado.set()

    hilo = threading.Thread(target=_seleccionar, daemon=True)
    hilo.start()
    terminado = completado.wait(timeout=3.0)

    if not terminado or not resultado:
        return {
            "sugerencias": list(_FALLBACK_SUGERENCIAS),
            "_fallback": True,
        }

    return resultado


# ---------------------------------------------------------------------------
# Tool 5: explicar_tema
# ---------------------------------------------------------------------------

@tool
def explicar_tema(
    usuario_id: int,
    tema: str,
    nivel: str = "básico",
) -> dict:
    """
    Genera una explicación adaptada al nivel del usuario sobre el tema solicitado.

    Parámetros:
        usuario_id (int): id del usuario.
        tema (str): tema a explicar (no vacío, máx. 200 caracteres).
        nivel (str): 'básico' o 'intermedio'.

    Devuelve:
        dict con ok=True y 'explicacion' (≤200 palabras), o ok=False con fuente_sugerida.
    """
    try:
        # Validaciones básicas
        if not tema or not tema.strip():
            return {
                "ok": False,
                "tema": tema,
                "explicacion": None,
                "fuente_sugerida": _FUENTES_ALTERNATIVAS["default"],
            }

        tema = tema.strip()[:200]

        if nivel not in ("básico", "intermedio"):
            nivel = "básico"

        # Biblioteca de explicaciones predefinidas (subset de temas comunes)
        explicaciones = _EXPLICACIONES_PREDEFINIDAS.get(
            _normalizar_tema(tema), None
        )

        if explicaciones:
            texto = explicaciones.get(nivel) or explicaciones.get("básico", "")
            return {
                "ok": True,
                "tema": tema,
                "nivel": nivel,
                "explicacion": texto,
                "fuente_sugerida": None,
            }

        # Tema no disponible en la biblioteca local
        return {
            "ok": False,
            "tema": tema,
            "explicacion": None,
            "fuente_sugerida": (
                f"Para este tema te recomiendo consultar a "
                f"{_fuente_para_tema(tema)}."
            ),
        }

    except Exception:  # noqa: BLE001
        logger.exception("Error inesperado en explicar_tema")
        return {
            "error": "No se pudo generar la explicación del tema solicitado. Inténtalo de nuevo en unos momentos."
        }


def _normalizar_tema(tema: str) -> str:
    """Normaliza el tema para buscar en la biblioteca predefinida."""
    mapa = {
        "tensión arterial": "tension_arterial",
        "presión arterial": "tension_arterial",
        "presión": "tension_arterial",
        "tensión": "tension_arterial",
        "diabetes": "diabetes",
        "azúcar en sangre": "diabetes",
        "glucosa": "diabetes",
        "sueño": "sueno",
        "dormir": "sueno",
        "insomnio": "sueno",
        "alimentación": "alimentacion",
        "dieta": "alimentacion",
        "nutrición": "alimentacion",
        "actividad física": "actividad_fisica",
        "ejercicio": "actividad_fisica",
        "caminar": "actividad_fisica",
        "smartphone": "smartphone",
        "teléfono inteligente": "smartphone",
        "móvil": "smartphone",
        "internet": "internet",
        "videollamada": "videollamada",
        "videollamadas": "videollamada",
    }
    tema_lower = tema.lower()
    for clave, valor in mapa.items():
        if clave in tema_lower:
            return valor
    return tema_lower.replace(" ", "_")


_EXPLICACIONES_PREDEFINIDAS: dict[str, dict[str, str]] = {
    "tension_arterial": {
        "básico": (
            "La tensión arterial es la fuerza con que la sangre empuja las paredes de las venas. "
            "Cuando es muy alta puede cansar el corazón. "
            "El médico la mide con un aparato llamado tensiómetro. "
            "Lo normal es que esté entre 90/60 y 120/80."
        ),
        "intermedio": (
            "La tensión arterial mide la presión que ejerce la sangre sobre las arterias. "
            "Se expresa con dos números: la presión sistólica (cuando el corazón late) "
            "y la presión diastólica (cuando el corazón descansa). "
            "La hipertensión (presión alta) ocurre cuando supera 140/90 de forma sostenida "
            "y aumenta el riesgo de enfermedades cardiovasculares. "
            "El médico puede recomendar cambios de estilo de vida o medicación."
        ),
    },
    "diabetes": {
        "básico": (
            "La diabetes es una enfermedad en la que el azúcar en sangre está muy alta. "
            "El cuerpo necesita insulina para usar ese azúcar como energía. "
            "Si no hay suficiente insulina, el azúcar se acumula. "
            "El médico puede ayudarte a controlarla con dieta y medicamentos."
        ),
        "intermedio": (
            "La diabetes es un trastorno metabólico caracterizado por hiperglucemia crónica. "
            "En la diabetes tipo 2, las células desarrollan resistencia a la insulina, "
            "hormona producida por el páncreas para regular la glucosa en sangre. "
            "El tratamiento incluye cambios en la alimentación, "
            "actividad física regular y, en algunos casos, hipoglucemiantes orales o insulina. "
            "El control regular de la glucemia es esencial."
        ),
    },
    "sueno": {
        "básico": (
            "Dormir bien es muy importante para la salud. "
            "Los adultos necesitan entre 7 y 9 horas de sueño cada noche. "
            "Acostarte a la misma hora cada día ayuda a descansar mejor. "
            "Evita la cafeína y las pantallas antes de dormir."
        ),
        "intermedio": (
            "El sueño reparador tiene fases distintas: el sueño REM y el sueño de ondas lentas. "
            "Durante el sueño profundo el cuerpo repara tejidos y consolida la memoria. "
            "La higiene del sueño incluye mantener un horario regular, "
            "controlar la temperatura del dormitorio y limitar la exposición a luz azul. "
            "El insomnio crónico puede aumentar el riesgo de enfermedades cardiovasculares."
        ),
    },
    "alimentacion": {
        "básico": (
            "Comer bien significa incluir frutas, verduras, proteínas y cereales cada día. "
            "Trata de comer poco azúcar y poca sal. "
            "Beber suficiente agua también es muy importante. "
            "Hacer varias comidas pequeñas al día ayuda a tener energía constante."
        ),
        "intermedio": (
            "Una dieta equilibrada aporta macronutrientes (carbohidratos, proteínas y lípidos) "
            "y micronutrientes (vitaminas y minerales) en las proporciones adecuadas. "
            "El índice glucémico indica qué tan rápido un alimento eleva la glucemia. "
            "Se recomienda limitar los alimentos ultraprocesados y el sodio "
            "para reducir el riesgo de hipertensión y enfermedades metabólicas."
        ),
    },
    "actividad_fisica": {
        "básico": (
            "Moverse cada día es muy bueno para la salud. "
            "Caminar 30 minutos al día ya marca una gran diferencia. "
            "No hace falta ir al gimnasio: subir escaleras o bailar en casa también cuenta. "
            "Empieza poco a poco y escucha a tu cuerpo."
        ),
        "intermedio": (
            "La actividad física regular mejora la capacidad cardiovascular y la sensibilidad a la insulina. "
            "La OMS recomienda al menos 150 minutos de actividad aeróbica moderada por semana. "
            "El entrenamiento de fuerza dos veces por semana ayuda a mantener la masa muscular, "
            "especialmente importante con el envejecimiento. "
            "El sedentarismo prolongado es un factor de riesgo independiente."
        ),
    },
    "smartphone": {
        "básico": (
            "Un teléfono inteligente es un teléfono que también puede conectarse a internet. "
            "Con él puedes llamar, mandar mensajes y ver fotos. "
            "También puedes hacer videollamadas para ver a tus familiares. "
            "El botón de inicio siempre te lleva a la pantalla principal."
        ),
        "intermedio": (
            "Un smartphone combina las funciones de teléfono con las de un ordenador portátil. "
            "Usa un sistema operativo (Android o iOS) que gestiona las aplicaciones. "
            "La conectividad incluye WiFi, datos móviles y Bluetooth. "
            "Las actualizaciones de software son parches de seguridad importantes "
            "que conviene instalar regularmente."
        ),
    },
    "internet": {
        "básico": (
            "Internet es una red que conecta millones de ordenadores en todo el mundo. "
            "Con internet puedes buscar información, ver vídeos y hablar con personas lejanas. "
            "Para usarlo necesitas una conexión WiFi o datos en tu teléfono. "
            "Es como una biblioteca enorme que siempre está abierta."
        ),
        "intermedio": (
            "Internet es una infraestructura global de redes interconectadas mediante el protocolo TCP/IP. "
            "El acceso puede ser por fibra óptica, cable o red móvil. "
            "El navegador web interpreta el lenguaje HTML para mostrar páginas. "
            "La seguridad incluye usar contraseñas robustas y conexiones cifradas (HTTPS)."
        ),
    },
    "videollamada": {
        "básico": (
            "Una videollamada es una llamada en la que puedes ver a la otra persona por la pantalla. "
            "Necesitas internet y una aplicación como WhatsApp o Zoom. "
            "Solo tienes que tocar el icono de cámara cuando llamas. "
            "Así puedes ver la cara de tus seres queridos aunque estén lejos."
        ),
        "intermedio": (
            "Las videollamadas transmiten audio y vídeo en tiempo real mediante protocolos como WebRTC. "
            "La calidad depende del ancho de banda disponible. "
            "Las aplicaciones más usadas son WhatsApp, FaceTime, Zoom y Google Meet. "
            "Para mayor privacidad conviene usar aplicaciones con cifrado de extremo a extremo."
        ),
    },
}
