"""
Fixtures compartidos para toda la suite de pruebas de Mi Amigo Max.
Proporciona: db_en_memoria, usuario_test, agente_mock.
"""

import os
import pytest
from unittest.mock import MagicMock

from db.setup import inicializar_db
from db import models as db_models


# ---------------------------------------------------------------------------
# Fixture: db_en_memoria
# ---------------------------------------------------------------------------


@pytest.fixture
def db_en_memoria(tmp_path):
    """
    Crea una base de datos SQLite en un directorio temporal, ejecuta
    inicializar_db y la cierra al finalizar el test.

    Devuelve:
        str: ruta al archivo .db temporal listo para usar.
    """
    ruta = str(tmp_path / "test_max_shared.db")
    inicializar_db(ruta)
    os.environ["DB_PATH"] = ruta
    yield ruta
    # Limpieza: el directorio tmp_path se borra automáticamente por pytest


# ---------------------------------------------------------------------------
# Fixture: usuario_test
# ---------------------------------------------------------------------------


@pytest.fixture
def usuario_test(db_en_memoria):
    """
    Crea un usuario de prueba en la DB en memoria y devuelve su usuario_id.

    Depende de: db_en_memoria.

    Devuelve:
        int: usuario_id del usuario creado.
    """
    uid = db_models.crear_usuario("UsuarioTest", ruta_db=db_en_memoria)
    return uid


# ---------------------------------------------------------------------------
# Fixture: agente_mock
# ---------------------------------------------------------------------------


@pytest.fixture
def agente_mock(db_en_memoria, usuario_test):
    """
    Crea un MaxAgent con el cliente Bedrock mockeado (sin llamadas reales a AWS).

    Depende de: db_en_memoria, usuario_test.

    Devuelve:
        MaxAgent: instancia con _agente_strands = None (modo fallback local).
    """
    from agent.max_agent import create_agent

    agente = create_agent(
        usuario_id=usuario_test,
        nombre_usuario="UsuarioTest",
        canal="cli",
        ruta_db=db_en_memoria,
    )
    # Desactivar Strands para que no llame a AWS en pruebas
    agente._agente_strands = None
    return agente


# ---------------------------------------------------------------------------
# Fixture auxiliar: sesion_test
# ---------------------------------------------------------------------------


@pytest.fixture
def sesion_test(db_en_memoria, usuario_test):
    """
    Crea una sesión de prueba asociada al usuario_test.

    Devuelve:
        int: sesion_id de la sesión creada.
    """
    return db_models.crear_sesion(usuario_test, "cli", ruta_db=db_en_memoria)
