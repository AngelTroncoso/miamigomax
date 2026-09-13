"""
Punto de entrada CLI de Mi Amigo Max.
Gestiona el ciclo de vida de la sesión, la entrada/salida por consola
y el manejo de señales del sistema operativo.
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from agent.max_agent import create_agent  # noqa: E402 — importado a nivel módulo para permitir mocking en tests

# ---------------------------------------------------------------------------
# Logging — configurar antes de cualquier importación del proyecto
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de presentación
# ---------------------------------------------------------------------------
_SEPARADOR = "─" * 45
_TITULO = "Mi Amigo Max — tu compañero de todos los días"

_BIENVENIDA_NUEVA = (
    "¡Hola! Soy Max, tu compañero de conversación. Estoy aquí para "
    "acompañarte en el día a día, ayudarte a llevar registro de tus hábitos "
    "y charlar sobre lo que necesites. No soy médico ni reemplazo a las "
    "personas que te quieren, pero sí puedo estar aquí cuando lo necesites. "
    "Escribe 'salir' o pulsa Ctrl+C en cualquier momento para terminar."
)


def _validar_nombre(nombre: str) -> bool:
    """
    Valida que el nombre del usuario cumpla las restricciones de longitud.

    Parámetros:
        nombre (str): nombre proporcionado por el usuario.

    Devuelve:
        bool: True si la longitud está entre 1 y 50 caracteres inclusivos.
    """
    return 1 <= len(nombre.strip()) <= 50


def _solicitar_nombre(argumento: str | None) -> str:
    """
    Devuelve un nombre válido, solicitándolo interactivamente si es necesario.

    Parámetros:
        argumento (str | None): valor del argumento --usuario, puede ser None.

    Devuelve:
        str: nombre válido (1–50 caracteres) ya normalizado con strip().
    """
    nombre = argumento.strip() if argumento else ""
    while not _validar_nombre(nombre):
        if nombre:
            print(
                "El nombre debe tener entre 1 y 50 caracteres. "
                "Por favor, inténtalo de nuevo."
            )
        try:
            nombre = input("¿Cómo te llamas? ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta pronto.")
            sys.exit(0)
    return nombre


def _verificar_entorno() -> None:
    """
    Comprueba que todas las variables de entorno requeridas estén definidas.

    Efecto:
        Si falta alguna variable, imprime la lista de nombres faltantes con
        referencia a .env.example y termina con sys.exit(1).
    """
    requeridas = ["AWS_REGION", "BEDROCK_MODEL_ID", "DB_PATH"]
    faltantes = [v for v in requeridas if not os.environ.get(v)]
    if faltantes:
        print(
            "Error: faltan las siguientes variables de entorno:\n"
            + "\n".join(f"  - {v}" for v in faltantes)
            + "\nConsulta el archivo .env.example para ver los valores de ejemplo."
        )
        sys.exit(1)


def _inicializar_base_de_datos(ruta_db: str) -> None:
    """
    Inicializa la base de datos SQLite si no existe todavía.

    Parámetros:
        ruta_db (str): ruta al archivo .db.

    Efecto:
        Crea el schema completo o no hace nada si ya existe.
        Si falla, imprime un mensaje descriptivo y termina con sys.exit(1).
    """
    from db.setup import inicializar_db
    try:
        inicializar_db(ruta_db)
    except Exception as e:  # noqa: BLE001
        print(
            f"Error: no se pudo inicializar la base de datos en '{ruta_db}'.\n"
            f"Causa posible: permisos insuficientes o disco lleno.\n"
            f"Detalle técnico: {e}"
        )
        sys.exit(1)


def _obtener_o_crear_usuario(nombre: str, ruta_db: str) -> dict:
    """
    Recupera el usuario de la DB o lo crea si no existe.

    Parámetros:
        nombre (str): nombre del usuario.
        ruta_db (str): ruta al archivo .db.

    Devuelve:
        dict: datos del usuario con al menos 'id' y 'nombre'.
    """
    from db import models as db_models
    usuario = db_models.obtener_usuario_por_nombre(nombre, ruta_db=ruta_db)
    if usuario is None:
        try:
            uid = db_models.crear_usuario(nombre, ruta_db=ruta_db)
            usuario = db_models.obtener_usuario_por_nombre(nombre, ruta_db=ruta_db)
        except Exception as e:  # noqa: BLE001
            print(
                f"Error: no se pudo registrar el usuario en '{ruta_db}'.\n"
                f"Verifica que la base de datos sea accesible.\nDetalle: {e}"
            )
            sys.exit(1)
    return usuario


def _mensaje_bienvenida(agente, nombre: str) -> str:
    """
    Genera el mensaje de bienvenida inicial según si es primera sesión o no.

    Parámetros:
        agente: instancia de MaxAgent.
        nombre (str): nombre del usuario.

    Devuelve:
        str: mensaje de bienvenida adaptado.
    """
    if agente.es_primera_sesion():
        return _BIENVENIDA_NUEVA
    return f"Hola de nuevo, {nombre}. ¿Cómo estás hoy?"


def main() -> None:
    """
    Punto de entrada principal de la CLI.

    Carga variables de entorno, verifica la configuración, inicializa la DB,
    solicita o valida el nombre del usuario y ejecuta el bucle de conversación
    hasta que el usuario escribe 'salir'/'exit' o presiona Ctrl+C.
    """
    # Cargar .env antes de leer os.environ
    load_dotenv()

    # Parsear argumentos
    parser = argparse.ArgumentParser(
        description="Mi Amigo Max — agente conversacional de acompañamiento"
    )
    parser.add_argument(
        "--usuario",
        type=str,
        default=None,
        help="Nombre del usuario (se solicita interactivamente si no se proporciona)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Ruta a la base de datos SQLite (por defecto: valor de DB_PATH en .env)",
    )
    args = parser.parse_args()

    # Verificar variables de entorno requeridas
    _verificar_entorno()

    # Resolver ruta de DB (--db tiene prioridad sobre DB_PATH)
    ruta_db = args.db or os.environ["DB_PATH"]

    # Inicializar DB
    _inicializar_base_de_datos(ruta_db)

    # Obtener nombre del usuario
    nombre = _solicitar_nombre(args.usuario)

    # Obtener o crear usuario en DB
    usuario = _obtener_o_crear_usuario(nombre, ruta_db)
    usuario_id = usuario["id"]

    # Crear instancia del agente
    agente = create_agent(usuario_id, nombre, canal="cli", ruta_db=ruta_db)

    # Presentación en consola
    print(f"\n{_SEPARADOR}")
    print(_TITULO)
    print(_SEPARADOR)
    bienvenida = _mensaje_bienvenida(agente, nombre)
    print(f"\nMax: {bienvenida}\n")

    # Ajustar nivel de log según variable de entorno
    nivel_log = os.environ.get("LOG_LEVEL", "WARNING").upper()
    logging.getLogger().setLevel(getattr(logging, nivel_log, logging.WARNING))

    # Bucle de conversación
    while True:
        try:
            entrada = input(f"{nombre}: ").strip()
        except KeyboardInterrupt:
            print()
            agente.cerrar_sesion()
            print("Max: Ha sido un placer acompañarte. ¡Cuídate mucho!")
            sys.exit(0)
        except EOFError:
            agente.cerrar_sesion()
            sys.exit(0)

        if not entrada:
            continue

        # Comandos de salida
        if entrada.lower() in ("salir", "exit"):
            agente.cerrar_sesion()
            print("Max: Ha sido un placer acompañarte. ¡Cuídate mucho!")
            sys.exit(0)

        # Generar respuesta
        try:
            respuesta = agente.chat(entrada)
            print(f"\nMax: {respuesta}\n")
        except KeyboardInterrupt:
            print()
            agente.cerrar_sesion()
            print("Max: Ha sido un placer acompañarte. ¡Cuídate mucho!")
            sys.exit(0)
        except Exception as e:  # noqa: BLE001
            # Errores de red o Bedrock: mostrar mensaje amigable y continuar
            logger.error("Error al generar respuesta: %s", e)
            print(
                "\nMax: En este momento tengo un problema de conexión. "
                "Por favor, inténtalo de nuevo en unos momentos.\n"
            )


if __name__ == "__main__":
    main()
