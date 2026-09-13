"""
Pruebas unitarias para app.py.
Mockean la capa del agente y la base de datos para verificar
el comportamiento de la CLI sin llamadas reales a AWS.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

import app  # pre-importar para que patch("app.create_agent") funcione correctamente

from db.setup import inicializar_db
from db import models as db_models


# ---------------------------------------------------------------------------
# Fixture: DB temporal
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Crea y devuelve la ruta de una DB temporal inicializada."""
    ruta = str(tmp_path / "test_cli.db")
    inicializar_db(ruta)
    return ruta


@pytest.fixture(autouse=True)
def entorno_cli(db_path, monkeypatch):
    """Configura las variables de entorno mínimas para la CLI y limpia sys.argv."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    monkeypatch.setenv("DB_PATH", db_path)
    # Argparse lee sys.argv[1:]; limpiarlo evita que pytest pase sus argumentos a main()
    monkeypatch.setattr("sys.argv", ["app.py"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agente_mock(nombre="TestUser", db_path=None, primera_sesion=True):
    """Crea un mock de MaxAgent con comportamiento básico."""
    agente = MagicMock()
    agente.es_primera_sesion.return_value = primera_sesion
    agente.chat.return_value = "Hola, estoy aquí para acompañarte."
    agente.cerrar_sesion.return_value = None
    return agente


# ---------------------------------------------------------------------------
# Tests: _validar_nombre
# ---------------------------------------------------------------------------


class TestValidarNombre:
    def test_nombre_valido(self):
        from app import _validar_nombre
        assert _validar_nombre("Rosa") is True

    def test_nombre_1_caracter(self):
        from app import _validar_nombre
        assert _validar_nombre("A") is True

    def test_nombre_50_caracteres(self):
        from app import _validar_nombre
        assert _validar_nombre("A" * 50) is True

    def test_nombre_vacio(self):
        from app import _validar_nombre
        assert _validar_nombre("") is False

    def test_nombre_solo_espacios(self):
        from app import _validar_nombre
        assert _validar_nombre("   ") is False

    def test_nombre_51_caracteres(self):
        from app import _validar_nombre
        assert _validar_nombre("A" * 51) is False


# ---------------------------------------------------------------------------
# Tests: _verificar_entorno
# ---------------------------------------------------------------------------


class TestVerificarEntorno:
    def test_variables_completas_no_sale(self):
        """Con todas las variables presentes, no debe llamar sys.exit."""
        from app import _verificar_entorno
        _verificar_entorno()  # no debe lanzar SystemExit

    def test_falta_aws_region(self, monkeypatch, capsys):
        from app import _verificar_entorno
        monkeypatch.delenv("AWS_REGION", raising=False)
        with pytest.raises(SystemExit) as exc:
            _verificar_entorno()
        assert exc.value.code == 1
        salida = capsys.readouterr().out
        assert "AWS_REGION" in salida
        assert ".env.example" in salida

    def test_falta_bedrock_model_id(self, monkeypatch, capsys):
        from app import _verificar_entorno
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
        with pytest.raises(SystemExit) as exc:
            _verificar_entorno()
        assert exc.value.code == 1
        salida = capsys.readouterr().out
        assert "BEDROCK_MODEL_ID" in salida

    def test_multiples_variables_faltantes_lista_completa(self, monkeypatch, capsys):
        from app import _verificar_entorno
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("DB_PATH", raising=False)
        with pytest.raises(SystemExit):
            _verificar_entorno()
        salida = capsys.readouterr().out
        assert "AWS_REGION" in salida
        assert "DB_PATH" in salida
        # No debe mostrar los valores de las variables correctas
        assert "BEDROCK_MODEL_ID" not in salida or "faltantes" in salida


# ---------------------------------------------------------------------------
# Tests: bienvenida primera sesión vs. sesión subsiguiente
# ---------------------------------------------------------------------------


class TestMensajeBienvenida:
    def test_primera_sesion_incluye_descripcion(self, db_path):
        from app import _mensaje_bienvenida, _BIENVENIDA_NUEVA
        agente_mock = _agente_mock(primera_sesion=True, db_path=db_path)
        msg = _mensaje_bienvenida(agente_mock, "Rosa")
        palabras = len(msg.split())
        assert 50 <= palabras <= 150, (
            f"Bienvenida primera sesión debe tener 50–150 palabras, tiene {palabras}"
        )
        assert "Rosa" not in msg or "Max" in msg  # puede o no incluir el nombre

    def test_sesion_subsiguiente_es_corta(self, db_path):
        from app import _mensaje_bienvenida
        agente_mock = _agente_mock(primera_sesion=False, db_path=db_path)
        msg = _mensaje_bienvenida(agente_mock, "Rosa")
        palabras = len(msg.split())
        assert palabras <= 30, (
            f"Saludo de retorno debe tener ≤30 palabras, tiene {palabras}"
        )
        assert "Rosa" in msg

    def test_sesion_subsiguiente_incluye_nombre(self, db_path):
        from app import _mensaje_bienvenida
        agente_mock = _agente_mock(primera_sesion=False, db_path=db_path)
        msg = _mensaje_bienvenida(agente_mock, "Carlos")
        assert "Carlos" in msg


# ---------------------------------------------------------------------------
# Tests: comando salir/exit
# ---------------------------------------------------------------------------


class TestComandoSalir:
    def test_salir_cierra_sesion(self, db_path, capsys, monkeypatch):
        """El comando 'salir' debe llamar cerrar_sesion() y hacer exit(0)."""
        agente = _agente_mock(db_path=db_path)
        agente.cerrar_sesion = MagicMock()
        monkeypatch.setattr("sys.argv", ["app.py", "--usuario", "Rosa"])

        with patch("builtins.input", side_effect=["salir"]):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit) as exc:
                    app.main()

        assert exc.value.code == 0
        agente.cerrar_sesion.assert_called_once()

    def test_exit_cierra_sesion(self, db_path, capsys, monkeypatch):
        """El comando 'EXIT' (mayúsculas) debe tratarse igual que 'salir'."""
        agente = _agente_mock(db_path=db_path)
        agente.cerrar_sesion = MagicMock()
        monkeypatch.setattr("sys.argv", ["app.py", "--usuario", "Rosa"])

        with patch("builtins.input", side_effect=["EXIT"]):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit) as exc:
                    app.main()

        assert exc.value.code == 0

    def test_despedida_max_20_palabras(self, db_path, capsys, monkeypatch):
        """El mensaje de despedida al salir debe tener ≤20 palabras."""
        agente = _agente_mock(db_path=db_path)
        monkeypatch.setattr("sys.argv", ["app.py", "--usuario", "Rosa"])

        with patch("builtins.input", side_effect=["salir"]):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit):
                    app.main()

        salida = capsys.readouterr().out
        lineas_max = [l for l in salida.splitlines() if l.startswith("Max:")]
        if lineas_max:
            despedida = lineas_max[-1].replace("Max:", "").strip()
            palabras = len(despedida.split())
            assert palabras <= 20, (
                f"Despedida excede 20 palabras ({palabras}): '{despedida}'"
            )


# ---------------------------------------------------------------------------
# Tests: KeyboardInterrupt
# ---------------------------------------------------------------------------


class TestKeyboardInterrupt:
    def test_ctrl_c_cierra_sesion(self, db_path, monkeypatch):
        """Ctrl+C durante la conversación debe cerrar sesión y hacer exit(0)."""
        agente = _agente_mock(db_path=db_path)
        agente.cerrar_sesion = MagicMock()
        monkeypatch.setattr("sys.argv", ["app.py", "--usuario", "Rosa"])

        # El primer input() es el turno de conversación; Ctrl+C lo interrumpe
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit) as exc:
                    app.main()

        assert exc.value.code == 0
        agente.cerrar_sesion.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: error HTTP de Bedrock — continuar sesión
# ---------------------------------------------------------------------------


class TestErrorBedrock:
    def test_error_bedrock_continua_sesion(self, db_path, capsys, monkeypatch):
        """Un error de Bedrock debe mostrar mensaje en español y continuar el bucle."""
        agente = _agente_mock(db_path=db_path)
        agente.chat.side_effect = [
            Exception("HTTP 503 Service Unavailable"),
            "Hola de nuevo",
        ]
        monkeypatch.setattr("sys.argv", ["app.py", "--usuario", "Rosa"])

        with patch("builtins.input", side_effect=["Hola", "salir"]):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit) as exc:
                    app.main()

        assert exc.value.code == 0
        salida = capsys.readouterr().out
        assert "conexión" in salida.lower() or "problema" in salida.lower()


# ---------------------------------------------------------------------------
# Tests: validación de nombre con argparse + input interactivo
# ---------------------------------------------------------------------------


class TestValidacionNombreInteractivo:
    def test_nombre_invalido_solicita_de_nuevo(self, db_path, capsys):
        """Si el nombre es inválido, debe volver a solicitarlo."""
        agente = _agente_mock(db_path=db_path)

        # Primero nombre vacío (inválido), luego nombre válido, luego salir
        with patch("builtins.input", side_effect=["", "Rosa", "salir"]):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit) as exc:
                    app.main()

        assert exc.value.code == 0

    def test_nombre_muy_largo_solicita_de_nuevo(self, db_path, capsys):
        """Si el nombre tiene >50 caracteres, debe volver a solicitarlo."""
        agente = _agente_mock(db_path=db_path)
        nombre_largo = "A" * 51

        with patch("builtins.input", side_effect=[nombre_largo, "Rosa", "salir"]):
            with patch("app.create_agent", return_value=agente):
                with pytest.raises(SystemExit) as exc:
                    app.main()

        assert exc.value.code == 0
        salida = capsys.readouterr().out
        assert "50" in salida  # debe mencionar el límite
