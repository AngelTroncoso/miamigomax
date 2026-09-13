"""
Módulo de inicialización de la base de datos SQLite para Mi Amigo Max.
Crea todas las tablas e índices en una única transacción atómica si no existen.
Se invoca automáticamente al importar el módulo si el archivo .db no existe.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

# DDL completo del schema
_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL UNIQUE,
    nivel_complejidad TEXT    NOT NULL DEFAULT 'básico'
                              CHECK (nivel_complejidad IN ('básico', 'intermedio')),
    fecha_registro    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sesiones (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
    canal            TEXT    NOT NULL CHECK (canal IN ('cli', 'streamlit')),
    timestamp_inicio TEXT    NOT NULL DEFAULT (datetime('now')),
    timestamp_fin    TEXT,
    duracion_minutos INTEGER
);

CREATE TABLE IF NOT EXISTS mensajes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    sesion_id  INTEGER NOT NULL REFERENCES sesiones(id),
    rol        TEXT    NOT NULL CHECK (rol IN ('usuario', 'max')),
    contenido  TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS habitos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    categoria  TEXT    NOT NULL CHECK (categoria IN ('sueño', 'alimentación', 'actividad')),
    valor      REAL    NOT NULL,
    unidad     TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS flags_derivacion (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id        INTEGER NOT NULL REFERENCES usuarios(id),
    sesion_id         INTEGER NOT NULL REFERENCES sesiones(id),
    timestamp         TEXT    NOT NULL DEFAULT (datetime('now')),
    nivel_riesgo      TEXT    NOT NULL CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto')),
    frases_detectadas TEXT    NOT NULL,
    accion_tomada     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mensajes_usuario
    ON mensajes(usuario_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_habitos_usuario
    ON habitos(usuario_id, categoria, timestamp);

CREATE INDEX IF NOT EXISTS idx_sesiones_usuario
    ON sesiones(usuario_id, timestamp_inicio);

CREATE INDEX IF NOT EXISTS idx_flags_usuario_sesion
    ON flags_derivacion(usuario_id, sesion_id);
"""


def inicializar_db(ruta_db: str) -> None:
    """
    Crea la base de datos y todas las tablas si no existen.

    Parámetros:
        ruta_db (str): ruta al archivo .db de SQLite.

    Efecto:
        Crea el archivo y ejecuta el schema completo en una sola transacción
        atómica. Si la base de datos ya existe y contiene las tablas, la
        operación es idempotente (no lanza error).
    """
    try:
        conn = sqlite3.connect(ruta_db)
        conn.execute("PRAGMA foreign_keys = ON")
        # executescript maneja su propia transacción
        conn.executescript(_DDL)
        conn.commit()
        conn.close()
        logger.info("Base de datos inicializada correctamente en: %s", ruta_db)
    except sqlite3.OperationalError as e:
        logger.error(
            "Error al inicializar la base de datos en '%s': %s", ruta_db, e
        )
        raise
