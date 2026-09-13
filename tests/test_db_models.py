"""
Pruebas unitarias y de propiedad para db/models.py.
Incluye la Propiedad 4 (límite de 50 mensajes) y la Propiedad 10 (round-trip nivel).
"""

import os
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from db.setup import inicializar_db
from db import models


# ---------------------------------------------------------------------------
# Fixture: DB en memoria via tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Crea y devuelve la ruta de una DB temporal inicializada."""
    ruta = str(tmp_path / "test_models.db")
    inicializar_db(ruta)
    return ruta


@pytest.fixture
def usuario_id(db_path):
    """Crea un usuario de prueba y devuelve su id."""
    return models.crear_usuario("TestUser", ruta_db=db_path)


@pytest.fixture
def sesion_id(db_path, usuario_id):
    """Crea una sesión de prueba y devuelve su id."""
    return models.crear_sesion(usuario_id, "cli", ruta_db=db_path)


# ---------------------------------------------------------------------------
# Tests unitarios: usuarios
# ---------------------------------------------------------------------------


class TestUsuarios:
    def test_crear_y_recuperar_usuario(self, db_path):
        """Crear un usuario y recuperarlo por nombre devuelve los datos correctos."""
        uid = models.crear_usuario("Rosa", ruta_db=db_path)
        usuario = models.obtener_usuario_por_nombre("Rosa", ruta_db=db_path)
        assert usuario is not None
        assert usuario["id"] == uid
        assert usuario["nombre"] == "Rosa"
        assert usuario["nivel_complejidad"] == "básico"

    def test_usuario_inexistente_devuelve_none(self, db_path):
        """Buscar un nombre que no existe debe devolver None."""
        resultado = models.obtener_usuario_por_nombre("Nadie", ruta_db=db_path)
        assert resultado is None

    def test_nombre_duplicado_lanza_error(self, db_path):
        """Intentar crear dos usuarios con el mismo nombre debe lanzar ValueError."""
        models.crear_usuario("Duplicado", ruta_db=db_path)
        with pytest.raises(ValueError, match="Duplicado"):
            models.crear_usuario("Duplicado", ruta_db=db_path)

    def test_actualizar_nivel_complejidad(self, db_path, usuario_id):
        """Actualizar el nivel debe persistirse correctamente."""
        models.actualizar_nivel_complejidad(usuario_id, "intermedio", ruta_db=db_path)
        usuario = models.obtener_usuario_por_nombre("TestUser", ruta_db=db_path)
        assert usuario["nivel_complejidad"] == "intermedio"

    def test_nivel_invalido_lanza_error(self, db_path, usuario_id):
        """Un nivel distinto de básico/intermedio debe lanzar ValueError."""
        with pytest.raises(ValueError):
            models.actualizar_nivel_complejidad(usuario_id, "avanzado", ruta_db=db_path)


# ---------------------------------------------------------------------------
# Tests unitarios: sesiones
# ---------------------------------------------------------------------------


class TestSesiones:
    def test_crear_sesion(self, db_path, usuario_id):
        """Crear una sesión debe devolver un id entero positivo."""
        sid = models.crear_sesion(usuario_id, "cli", ruta_db=db_path)
        assert isinstance(sid, int)
        assert sid > 0

    def test_cerrar_sesion_actualiza_campos(self, db_path, usuario_id):
        """Cerrar sesión debe actualizar timestamp_fin y duracion_minutos."""
        import sqlite3
        sid = models.crear_sesion(usuario_id, "streamlit", ruta_db=db_path)
        models.cerrar_sesion(sid, ruta_db=db_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT timestamp_fin, duracion_minutos FROM sesiones WHERE id = ?",
            (sid,),
        ).fetchone()
        conn.close()
        assert row[0] is not None, "timestamp_fin no debe ser NULL tras cerrar sesión"
        assert row[1] is not None, "duracion_minutos no debe ser NULL tras cerrar sesión"
        assert row[1] >= 0

    def test_contar_sesiones_hoy_sin_sesiones(self, db_path):
        """Un usuario sin sesiones hoy debe devolver 0."""
        uid = models.crear_usuario("SinSesiones", ruta_db=db_path)
        assert models.contar_sesiones_hoy(uid, ruta_db=db_path) == 0

    def test_contar_sesiones_hoy_con_sesiones(self, db_path, usuario_id):
        """El conteo debe reflejar las sesiones creadas hoy."""
        models.crear_sesion(usuario_id, "cli", ruta_db=db_path)
        models.crear_sesion(usuario_id, "cli", ruta_db=db_path)
        assert models.contar_sesiones_hoy(usuario_id, ruta_db=db_path) == 2


# ---------------------------------------------------------------------------
# Tests unitarios: mensajes
# ---------------------------------------------------------------------------


class TestMensajes:
    def test_guardar_y_recuperar_mensaje(self, db_path, usuario_id, sesion_id):
        """Un mensaje guardado debe aparecer en el historial."""
        models.guardar_mensaje(
            sesion_id, "usuario", "Hola Max", usuario_id, ruta_db=db_path
        )
        historial = models.obtener_historial(usuario_id, ruta_db=db_path)
        assert len(historial) == 1
        assert historial[0]["contenido"] == "Hola Max"
        assert historial[0]["rol"] == "usuario"

    def test_historial_orden_cronologico(self, db_path, usuario_id, sesion_id):
        """El historial debe devolver mensajes en orden cronológico ascendente."""
        for i in range(3):
            models.guardar_mensaje(
                sesion_id, "usuario", f"Mensaje {i}", usuario_id, ruta_db=db_path
            )
        historial = models.obtener_historial(usuario_id, ruta_db=db_path)
        contenidos = [m["contenido"] for m in historial]
        assert contenidos == ["Mensaje 0", "Mensaje 1", "Mensaje 2"]


# ---------------------------------------------------------------------------
# Propiedad 4: Invariante de límite de 50 mensajes
# ---------------------------------------------------------------------------


@settings(max_examples=5, deadline=None)
@given(st.integers(min_value=51, max_value=100))
def test_limite_50_mensajes_invariante(n):
    """
    Propiedad 4: Insertar N>50 mensajes para el mismo usuario debe
    mantener COUNT(*) == 50 siempre.
    """
    import sqlite3 as _sqlite3
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop4.db")
        inicializar_db(ruta)
        uid = models.crear_usuario("PropUser4", ruta_db=ruta)
        sid = models.crear_sesion(uid, "cli", ruta_db=ruta)

        for i in range(n):
            models.guardar_mensaje(sid, "usuario", f"msg {i}", uid, ruta_db=ruta)

        conn = _sqlite3.connect(ruta)
        count = conn.execute(
            "SELECT COUNT(*) FROM mensajes WHERE usuario_id = ?", (uid,)
        ).fetchone()[0]
        conn.close()

        assert count == 50, (
            f"Se esperaban 50 mensajes tras insertar {n}, pero hay {count}"
        )


# ---------------------------------------------------------------------------
# Tests unitarios: hábitos
# ---------------------------------------------------------------------------


class TestHabitos:
    def test_insertar_habito(self, db_path, usuario_id):
        """Insertar un hábito debe registrarse sin error."""
        models.insertar_habito(usuario_id, "sueño", 7.5, "horas", ruta_db=db_path)
        habitos = models.obtener_habitos_periodo(usuario_id, 7, ruta_db=db_path)
        assert len(habitos) == 1
        assert habitos[0]["categoria"] == "sueño"
        assert habitos[0]["valor"] == 7.5

    def test_habitos_periodo_vacio(self, db_path, usuario_id):
        """Si no hay hábitos, debe devolver una lista vacía."""
        resultado = models.obtener_habitos_periodo(usuario_id, 7, ruta_db=db_path)
        assert resultado == []


# ---------------------------------------------------------------------------
# Tests unitarios: flags de derivación
# ---------------------------------------------------------------------------


class TestFlagsDerivacion:
    def test_sin_flags_devuelve_false(self, db_path, usuario_id, sesion_id):
        """Sin flags insertados, tiene_flag_derivacion_activo debe devolver False."""
        assert (
            models.tiene_flag_derivacion_activo(usuario_id, sesion_id, ruta_db=db_path)
            is False
        )

    def test_con_flag_devuelve_true(self, db_path, usuario_id, sesion_id):
        """Tras insertar un flag, la función debe devolver True."""
        models.insertar_flag_derivacion(
            usuario_id=usuario_id,
            nivel_riesgo="alto",
            frases_detectadas=["me siento solo"],
            accion_tomada="Derivación indicada al usuario",
            sesion_id=sesion_id,
            ruta_db=db_path,
        )
        assert (
            models.tiene_flag_derivacion_activo(usuario_id, sesion_id, ruta_db=db_path)
            is True
        )


# ---------------------------------------------------------------------------
# Propiedad 10: Round-trip de nivel de complejidad
# ---------------------------------------------------------------------------


@settings(max_examples=10)
@given(st.sampled_from(["básico", "intermedio"]))
def test_round_trip_nivel_complejidad(nivel):
    """
    Propiedad 10: Persistir nivel_complejidad y recuperarlo en nueva sesión
    debe devolver exactamente el mismo valor sin recalcular.
    """
    import tempfile, os

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop10.db")
        inicializar_db(ruta)
        uid = models.crear_usuario("PropUser10", ruta_db=ruta)
        models.actualizar_nivel_complejidad(uid, nivel, ruta_db=ruta)

        # Simular nueva sesión: recuperar usuario de nuevo
        usuario = models.obtener_usuario_por_nombre("PropUser10", ruta_db=ruta)
        assert usuario["nivel_complejidad"] == nivel, (
            f"Se esperaba nivel '{nivel}', se obtuvo '{usuario['nivel_complejidad']}'"
        )
