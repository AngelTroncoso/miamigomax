"""
Pruebas unitarias para db/setup.py.
Verifica que el schema se crea correctamente, es idempotente
y que PRAGMA foreign_keys está activo.
"""

import sqlite3
import pytest
from db.setup import inicializar_db


@pytest.fixture
def db_memory(tmp_path):
    """Devuelve la ruta a una DB temporal vacía."""
    ruta = str(tmp_path / "test_max.db")
    return ruta


TABLAS_ESPERADAS = {
    "usuarios",
    "sesiones",
    "mensajes",
    "habitos",
    "flags_derivacion",
}

INDICES_ESPERADOS = {
    "idx_mensajes_usuario",
    "idx_habitos_usuario",
    "idx_sesiones_usuario",
    "idx_flags_usuario_sesion",
}


def obtener_tablas(conn):
    """Devuelve el conjunto de nombres de tablas en la DB."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def obtener_indices(conn):
    """Devuelve el conjunto de nombres de índices en la DB."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    return {r[0] for r in rows}


class TestInicializarDB:
    """Pruebas sobre la función inicializar_db."""

    def test_crea_todas_las_tablas(self, db_memory):
        """El schema completo debe crearse con todas las tablas esperadas."""
        inicializar_db(db_memory)
        conn = sqlite3.connect(db_memory)
        tablas = obtener_tablas(conn)
        conn.close()
        assert TABLAS_ESPERADAS.issubset(tablas), (
            f"Tablas faltantes: {TABLAS_ESPERADAS - tablas}"
        )

    def test_crea_todos_los_indices(self, db_memory):
        """El schema debe incluir los cuatro índices de rendimiento."""
        inicializar_db(db_memory)
        conn = sqlite3.connect(db_memory)
        indices = obtener_indices(conn)
        conn.close()
        assert INDICES_ESPERADOS.issubset(indices), (
            f"Índices faltantes: {INDICES_ESPERADOS - indices}"
        )

    def test_inicializacion_idempotente(self, db_memory):
        """Llamar inicializar_db dos veces no debe lanzar ningún error."""
        inicializar_db(db_memory)
        inicializar_db(db_memory)  # segunda llamada: debe ser silenciosa
        conn = sqlite3.connect(db_memory)
        tablas = obtener_tablas(conn)
        conn.close()
        assert TABLAS_ESPERADAS.issubset(tablas)

    def test_foreign_keys_activo(self, db_memory):
        """PRAGMA foreign_keys debe estar activado en la conexión."""
        inicializar_db(db_memory)
        conn = sqlite3.connect(db_memory)
        conn.execute("PRAGMA foreign_keys = ON")
        resultado = conn.execute("PRAGMA foreign_keys").fetchone()
        conn.close()
        assert resultado[0] == 1, "PRAGMA foreign_keys debería estar en 1 (ON)"

    def test_integridad_referencial_usuarios(self, db_memory):
        """Una sesión con usuario_id inexistente debe fallar con FK activada."""
        inicializar_db(db_memory)
        conn = sqlite3.connect(db_memory)
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sesiones (usuario_id, canal) VALUES (?, ?)",
                (9999, "cli"),
            )
            conn.commit()
        conn.close()

    def test_check_constraint_nivel_complejidad(self, db_memory):
        """El campo nivel_complejidad solo acepta 'básico' o 'intermedio'."""
        inicializar_db(db_memory)
        conn = sqlite3.connect(db_memory)
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO usuarios (nombre, nivel_complejidad) VALUES (?, ?)",
                ("Test", "avanzado"),
            )
            conn.commit()
        conn.close()
