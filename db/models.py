"""
Módulo de acceso a datos para Mi Amigo Max.
Contiene todas las funciones de lectura y escritura sobre la base de datos SQLite.
No incluye lógica de negocio; solo operaciones CRUD.
"""

import json
import os
import sqlite3
import logging
from datetime import datetime, date, timezone

logger = logging.getLogger(__name__)

# La ruta de la DB se resuelve en tiempo de ejecución desde la variable de entorno.
# Las funciones reciben opcionalmente una conexión para facilitar las pruebas.


def _get_db_path() -> str:
    """Devuelve la ruta a la base de datos desde la variable de entorno DB_PATH."""
    return os.environ.get("DB_PATH", "max_data.db")


def _connect(ruta_db: str | None = None) -> sqlite3.Connection:
    """
    Abre una conexión SQLite con foreign_keys activado.

    Parámetros:
        ruta_db (str | None): ruta al archivo .db; si es None usa DB_PATH.

    Devuelve:
        sqlite3.Connection con row_factory configurado para devolver dicts.
    """
    ruta = ruta_db or _get_db_path()
    conn = sqlite3.connect(ruta)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------


def crear_usuario(nombre: str, ruta_db: str | None = None) -> int:
    """
    Crea un nuevo usuario en la base de datos.

    Parámetros:
        nombre (str): nombre del usuario (único, 1–50 caracteres).
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        int: el id del usuario recién creado.
    """
    try:
        conn = _connect(ruta_db)
        cur = conn.execute(
            "INSERT INTO usuarios (nombre) VALUES (?)", (nombre,)
        )
        conn.commit()
        usuario_id = cur.lastrowid
        conn.close()
        return usuario_id
    except sqlite3.IntegrityError as e:
        raise ValueError(
            f"Ya existe un usuario con el nombre '{nombre}': {e}"
        ) from e
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"No se pudo crear el usuario en '{ruta_db or _get_db_path()}': {e}"
        ) from e


def obtener_usuario_por_nombre(
    nombre: str, ruta_db: str | None = None
) -> dict | None:
    """
    Busca un usuario por su nombre exacto.

    Parámetros:
        nombre (str): nombre del usuario a buscar.
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        dict con los datos del usuario, o None si no existe.
    """
    try:
        conn = _connect(ruta_db)
        row = conn.execute(
            "SELECT * FROM usuarios WHERE nombre = ?", (nombre,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"Error al buscar usuario en '{ruta_db or _get_db_path()}': {e}"
        ) from e


def actualizar_nivel_complejidad(
    usuario_id: int, nivel: str, ruta_db: str | None = None
) -> None:
    """
    Actualiza el nivel de complejidad preferido del usuario.

    Parámetros:
        usuario_id (int): identificador del usuario.
        nivel (str): 'básico' o 'intermedio'.
        ruta_db (str | None): ruta opcional al archivo .db.

    Efecto:
        Actualiza el campo nivel_complejidad en la tabla usuarios.
    """
    if nivel not in ("básico", "intermedio"):
        raise ValueError(
            f"Nivel inválido '{nivel}'. Debe ser 'básico' o 'intermedio'."
        )
    try:
        conn = _connect(ruta_db)
        conn.execute(
            "UPDATE usuarios SET nivel_complejidad = ? WHERE id = ?",
            (nivel, usuario_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        raise RuntimeError(
            f"No se pudo actualizar el nivel en '{ruta_db or _get_db_path()}': {e}"
        ) from e


# ---------------------------------------------------------------------------
# Sesiones
# ---------------------------------------------------------------------------


def crear_sesion(
    usuario_id: int, canal: str, ruta_db: str | None = None
) -> int:
    """
    Registra el inicio de una nueva sesión de conversación.

    Parámetros:
        usuario_id (int): id del usuario.
        canal (str): 'cli' o 'streamlit'.
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        int: el id de la sesión creada.
    """
    try:
        conn = _connect(ruta_db)
        cur = conn.execute(
            "INSERT INTO sesiones (usuario_id, canal) VALUES (?, ?)",
            (usuario_id, canal),
        )
        conn.commit()
        sesion_id = cur.lastrowid
        conn.close()
        return sesion_id
    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        raise RuntimeError(
            f"No se pudo crear la sesión en '{ruta_db or _get_db_path()}': {e}"
        ) from e


def cerrar_sesion(sesion_id: int, ruta_db: str | None = None) -> None:
    """
    Registra el cierre de una sesión actualizando timestamp_fin y duracion_minutos.

    Parámetros:
        sesion_id (int): id de la sesión a cerrar.
        ruta_db (str | None): ruta opcional al archivo .db.

    Efecto:
        Actualiza timestamp_fin y duracion_minutos en la tabla sesiones.
    """
    try:
        conn = _connect(ruta_db)
        row = conn.execute(
            "SELECT timestamp_inicio FROM sesiones WHERE id = ?", (sesion_id,)
        ).fetchone()
        if row:
            inicio = datetime.fromisoformat(row["timestamp_inicio"])
            fin = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC para consistencia con SQLite
            duracion = int((fin - inicio).total_seconds() / 60)
            conn.execute(
                """UPDATE sesiones
                   SET timestamp_fin = ?, duracion_minutos = ?
                   WHERE id = ?""",
                (fin.isoformat(sep=" "), duracion, sesion_id),
            )
            conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.error(
            "No se pudo cerrar la sesión %d en '%s': %s",
            sesion_id,
            ruta_db or _get_db_path(),
            e,
        )


def contar_sesiones_hoy(
    usuario_id: int, ruta_db: str | None = None
) -> int:
    """
    Cuenta cuántas sesiones ha iniciado el usuario en el día de hoy.

    Parámetros:
        usuario_id (int): id del usuario.
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        int: número de sesiones del día actual (0 si no hay ninguna).
    """
    try:
        conn = _connect(ruta_db)
        hoy = date.today().isoformat()
        row = conn.execute(
            """SELECT COUNT(*) AS cnt FROM sesiones
               WHERE usuario_id = ?
                 AND date(timestamp_inicio) = ?""",
            (usuario_id, hoy),
        ).fetchone()
        conn.close()
        return row["cnt"] if row else 0
    except sqlite3.OperationalError as e:
        logger.error(
            "No se pudo contar las sesiones de hoy para usuario %d: %s",
            usuario_id,
            e,
        )
        return 0


# ---------------------------------------------------------------------------
# Mensajes
# ---------------------------------------------------------------------------


def guardar_mensaje(
    sesion_id: int,
    rol: str,
    contenido: str,
    usuario_id: int,
    ruta_db: str | None = None,
) -> None:
    """
    Persiste un mensaje en la tabla mensajes aplicando el límite de 50 por usuario.

    Parámetros:
        sesion_id (int): id de la sesión activa.
        rol (str): 'usuario' o 'max'.
        contenido (str): texto del mensaje.
        usuario_id (int): id del usuario (necesario para el límite).
        ruta_db (str | None): ruta opcional al archivo .db.

    Efecto:
        Si ya hay 50 mensajes del usuario, elimina el más antiguo antes de insertar.
    """
    try:
        conn = _connect(ruta_db)
        with conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM mensajes WHERE usuario_id = ?",
                (usuario_id,),
            ).fetchone()["cnt"]
            if count >= 50:
                conn.execute(
                    """DELETE FROM mensajes
                       WHERE id = (
                           SELECT MIN(id) FROM mensajes WHERE usuario_id = ?
                       )""",
                    (usuario_id,),
                )
            conn.execute(
                """INSERT INTO mensajes (usuario_id, sesion_id, rol, contenido)
                   VALUES (?, ?, ?, ?)""",
                (usuario_id, sesion_id, rol, contenido),
            )
        conn.close()
    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        logger.error(
            "No se pudo guardar el mensaje en '%s': %s",
            ruta_db or _get_db_path(),
            e,
        )


def obtener_historial(
    usuario_id: int, limite: int = 50, ruta_db: str | None = None
) -> list[dict]:
    """
    Obtiene los últimos N mensajes del usuario ordenados cronológicamente.

    Parámetros:
        usuario_id (int): id del usuario.
        limite (int): número máximo de mensajes a devolver (por defecto 50).
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        list[dict]: lista de mensajes con claves rol, contenido y timestamp.
    """
    try:
        conn = _connect(ruta_db)
        rows = conn.execute(
            """SELECT rol, contenido, timestamp FROM mensajes
               WHERE usuario_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (usuario_id, limite),
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]
    except sqlite3.OperationalError as e:
        logger.error("Error al obtener historial: %s", e)
        return []


def obtener_ultimos_n_mensajes(
    usuario_id: int, n: int, ruta_db: str | None = None
) -> list[dict]:
    """
    Devuelve los últimos N mensajes del usuario para análisis de contexto.

    Parámetros:
        usuario_id (int): id del usuario.
        n (int): cantidad de mensajes a recuperar.
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        list[dict]: lista de dicts con claves rol y contenido, orden cronológico.
    """
    return obtener_historial(usuario_id, limite=n, ruta_db=ruta_db)


# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------


def insertar_habito(
    usuario_id: int,
    categoria: str,
    valor: float,
    unidad: str,
    ruta_db: str | None = None,
) -> None:
    """
    Persiste un registro de hábito en la tabla habitos.

    Parámetros:
        usuario_id (int): id del usuario.
        categoria (str): 'sueño', 'alimentación' o 'actividad'.
        valor (float): valor numérico del hábito.
        unidad (str): unidad de medida (ej. 'horas', 'porciones', 'minutos').
        ruta_db (str | None): ruta opcional al archivo .db.

    Efecto:
        Inserta una fila en la tabla habitos.
    """
    try:
        conn = _connect(ruta_db)
        conn.execute(
            """INSERT INTO habitos (usuario_id, categoria, valor, unidad)
               VALUES (?, ?, ?, ?)""",
            (usuario_id, categoria, valor, unidad),
        )
        conn.commit()
        conn.close()
    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        raise RuntimeError(
            f"No se pudo insertar el hábito en '{ruta_db or _get_db_path()}': {e}"
        ) from e


def obtener_habitos_periodo(
    usuario_id: int, dias: int, ruta_db: str | None = None
) -> list[dict]:
    """
    Devuelve los hábitos registrados en los últimos N días para un usuario.

    Parámetros:
        usuario_id (int): id del usuario.
        dias (int): ventana de tiempo en días (1–30).
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        list[dict]: lista de registros de hábitos con todas sus columnas.
    """
    try:
        conn = _connect(ruta_db)
        rows = conn.execute(
            """SELECT id, usuario_id, categoria, valor, unidad, timestamp
               FROM habitos
               WHERE usuario_id = ?
                 AND timestamp >= datetime('now', ? || ' days')
               ORDER BY timestamp ASC""",
            (usuario_id, f"-{dias}"),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError as e:
        logger.error("Error al obtener hábitos del período: %s", e)
        return []


# ---------------------------------------------------------------------------
# Flags de derivación
# ---------------------------------------------------------------------------


def insertar_flag_derivacion(
    usuario_id: int,
    nivel_riesgo: str,
    frases_detectadas: list[str],
    accion_tomada: str,
    sesion_id: int,
    ruta_db: str | None = None,
) -> None:
    """
    Registra un flag de derivación ante detección de señal de riesgo.

    Parámetros:
        usuario_id (int): id del usuario.
        nivel_riesgo (str): 'bajo', 'medio' o 'alto'.
        frases_detectadas (list[str]): fragmentos del texto que motivaron el flag.
        accion_tomada (str): descripción de la acción ejecutada.
        sesion_id (int): id de la sesión activa.
        ruta_db (str | None): ruta opcional al archivo .db.

    Efecto:
        Inserta una fila en flags_derivacion con frases_detectadas serializado como JSON.
    """
    try:
        conn = _connect(ruta_db)
        conn.execute(
            """INSERT INTO flags_derivacion
               (usuario_id, sesion_id, nivel_riesgo, frases_detectadas, accion_tomada)
               VALUES (?, ?, ?, ?, ?)""",
            (
                usuario_id,
                sesion_id,
                nivel_riesgo,
                json.dumps(frases_detectadas, ensure_ascii=False),
                accion_tomada,
            ),
        )
        conn.commit()
        conn.close()
    except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        raise RuntimeError(
            f"No se pudo insertar el flag de derivación en "
            f"'{ruta_db or _get_db_path()}': {e}"
        ) from e


def tiene_flag_derivacion_activo(
    usuario_id: int, sesion_id: int, ruta_db: str | None = None
) -> bool:
    """
    Comprueba si existe algún flag de derivación activo en la sesión indicada.

    Parámetros:
        usuario_id (int): id del usuario.
        sesion_id (int): id de la sesión a consultar.
        ruta_db (str | None): ruta opcional al archivo .db.

    Devuelve:
        bool: True si hay al menos un flag de derivación para esa sesión.
    """
    try:
        conn = _connect(ruta_db)
        row = conn.execute(
            """SELECT COUNT(*) AS cnt FROM flags_derivacion
               WHERE usuario_id = ? AND sesion_id = ?""",
            (usuario_id, sesion_id),
        ).fetchone()
        conn.close()
        return row["cnt"] > 0 if row else False
    except sqlite3.OperationalError as e:
        logger.error("Error al verificar flag de derivación: %s", e)
        return False
