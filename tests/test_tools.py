"""
Pruebas unitarias y de propiedad para agent/tools.py.
Incluye Propiedades 2, 3, 5, 6, 7, 8 y 9 de Hypothesis.
Todas las pruebas operan con una DB en memoria (tmp_path) sin llamadas a AWS.
"""

import os
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from db.setup import inicializar_db
from db import models as db_models


# ---------------------------------------------------------------------------
# Fixture: DB temporal + usuario + sesión
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path):
    """Devuelve la ruta de una DB temporal inicializada."""
    ruta = str(tmp_path / "test_tools.db")
    inicializar_db(ruta)
    return ruta


@pytest.fixture
def usuario(db_path):
    """Crea un usuario de prueba y devuelve (usuario_id, sesion_id)."""
    uid = db_models.crear_usuario("TestTools", ruta_db=db_path)
    sid = db_models.crear_sesion(uid, "cli", ruta_db=db_path)
    return uid, sid


# ---------------------------------------------------------------------------
# Helpers para inyectar la ruta de DB en las tools
# ---------------------------------------------------------------------------
# Las tools usan db_models que lee DB_PATH del entorno.
# Para tests, sobreescribimos DB_PATH via os.environ.


def _set_db(monkeypatch, db_path):
    monkeypatch.setenv("DB_PATH", db_path)


# ---------------------------------------------------------------------------
# Tests unitarios: registrar_habito
# ---------------------------------------------------------------------------

class TestRegistrarHabito:
    def test_registro_valido_sueno(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        resultado = registrar_habito(uid, "sueño", 7.0, "horas")
        assert resultado.get("ok") is True
        assert "mensaje" in resultado

    def test_registro_valido_alimentacion(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        resultado = registrar_habito(uid, "alimentación", 3.0, "porciones")
        assert resultado.get("ok") is True

    def test_registro_valido_actividad(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        resultado = registrar_habito(uid, "actividad", 30.0, "minutos")
        assert resultado.get("ok") is True

    def test_categoria_invalida(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        resultado = registrar_habito(uid, "meditación", 1.0, "horas")
        assert resultado.get("ok") is False
        assert "error" in resultado

    def test_valor_fuera_rango_sueno(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        resultado = registrar_habito(uid, "sueño", 25.0, "horas")
        assert resultado.get("ok") is False
        assert "rango" in resultado.get("error", "").lower() or "fuera" in resultado.get("error", "").lower()

    def test_unidad_vacia_rechazada(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        resultado = registrar_habito(uid, "sueño", 7.0, "")
        assert resultado.get("ok") is False

    def test_no_persiste_si_validacion_falla(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito
        uid, _ = usuario
        registrar_habito(uid, "sueño", 999.0, "horas")
        habitos = db_models.obtener_habitos_periodo(uid, 7, ruta_db=db_path)
        assert len(habitos) == 0


# ---------------------------------------------------------------------------
# Propiedad 2: Round-trip de persistencia de hábitos
# ---------------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(
    categoria=st.sampled_from(["sueño", "alimentación", "actividad"]),
    valor=st.one_of(
        st.floats(min_value=0.0, max_value=24.0, allow_nan=False, allow_infinity=False),   # sueño
        st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),   # alimentación
        st.floats(min_value=0.0, max_value=600.0, allow_nan=False, allow_infinity=False),  # actividad
    ),
    unidad=st.text(min_size=1, max_size=20).filter(str.strip),
)
def test_round_trip_persistencia_habitos(categoria, valor, unidad):
    """
    Propiedad 2: Registrar un hábito válido y consultarlo con obtener_resumen_habitos
    debe mostrar el dato persistido.
    """
    import tempfile

    # Ajustar valor al rango de la categoría para que sea siempre válido
    rangos = {"sueño": (0, 24), "alimentación": (0, 20), "actividad": (0, 600)}
    minv, maxv = rangos[categoria]
    valor_ajustado = max(minv, min(maxv, valor))
    assume(valor_ajustado >= 0)

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop2.db")
        inicializar_db(ruta)
        os.environ["DB_PATH"] = ruta
        uid = db_models.crear_usuario("PropUser2", ruta_db=ruta)
        db_models.crear_sesion(uid, "cli", ruta_db=ruta)

        from agent.tools import registrar_habito, obtener_resumen_habitos

        r = registrar_habito(uid, categoria, valor_ajustado, unidad.strip())
        assert r.get("ok") is True, f"Registro falló: {r}"

        resumen = obtener_resumen_habitos(uid, 7)
        assert resumen.get("ok") is True
        assert categoria in resumen.get("resumen", {}), (
            f"Categoría '{categoria}' no encontrada en resumen: {resumen}"
        )


# ---------------------------------------------------------------------------
# Propiedad 3: Rechazo de valores fuera de rango
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    categoria=st.sampled_from(["sueño", "alimentación", "actividad"]),
    valor=st.floats(allow_nan=False, allow_infinity=False),
)
def test_rechazo_valores_fuera_de_rango(categoria, valor):
    """
    Propiedad 3: Valores fuera de rango deben ser rechazados y no persistidos.
    """
    rangos = {"sueño": (0, 24), "alimentación": (0, 20), "actividad": (0, 600)}
    minv, maxv = rangos[categoria]

    # Solo ejecutar con valores genuinamente fuera de rango
    assume(valor < minv or valor > maxv)

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop3.db")
        inicializar_db(ruta)
        os.environ["DB_PATH"] = ruta
        uid = db_models.crear_usuario("PropUser3", ruta_db=ruta)

        from agent.tools import registrar_habito

        resultado = registrar_habito(uid, categoria, valor, "unidad")
        assert resultado.get("ok") is False or "error" in resultado, (
            f"Se esperaba rechazo para {categoria}={valor}, obtuvo: {resultado}"
        )

        habitos = db_models.obtener_habitos_periodo(uid, 7, ruta_db=ruta)
        assert len(habitos) == 0, (
            f"No debería haberse persistido ningún hábito fuera de rango"
        )


# ---------------------------------------------------------------------------
# Tests unitarios: obtener_resumen_habitos
# ---------------------------------------------------------------------------

class TestObtenerResumenHabitos:
    def test_sin_registros_devuelve_mensaje(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import obtener_resumen_habitos
        uid, _ = usuario
        resultado = obtener_resumen_habitos(uid, 7)
        assert resultado.get("ok") is True
        assert resultado.get("resumen") == {}
        assert "mensaje" in resultado

    def test_con_registros_calcula_promedio(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import registrar_habito, obtener_resumen_habitos
        uid, _ = usuario
        registrar_habito(uid, "sueño", 6.0, "horas")
        registrar_habito(uid, "sueño", 8.0, "horas")
        resumen = obtener_resumen_habitos(uid, 7)
        assert resumen["resumen"]["sueño"]["promedio_diario"] == 7.0


# ---------------------------------------------------------------------------
# Tests unitarios: detectar_senal_riesgo
# ---------------------------------------------------------------------------

class TestDetectarSenalRiesgo:
    def test_texto_neutro_es_bajo(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import detectar_senal_riesgo
        uid, _ = usuario
        resultado = detectar_senal_riesgo(uid, "Hoy hace buen tiempo", [])
        assert resultado["nivel"] == "bajo"
        assert isinstance(resultado["frases_detectadas"], list)

    def test_texto_riesgo_alto(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import detectar_senal_riesgo
        uid, _ = usuario
        resultado = detectar_senal_riesgo(
            uid, "no quiero vivir más, ya no quiero estar", []
        )
        assert resultado["nivel"] == "alto"

    def test_texto_medio(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import detectar_senal_riesgo
        uid, _ = usuario
        resultado = detectar_senal_riesgo(uid, "me siento solo y muy triste", [])
        assert resultado["nivel"] in ("medio", "alto")

    def test_texto_vacio_devuelve_bajo(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import detectar_senal_riesgo
        uid, _ = usuario
        resultado = detectar_senal_riesgo(uid, "", [])
        assert resultado["nivel"] == "bajo"


# ---------------------------------------------------------------------------
# Propiedad 5: Contrato de retorno de detectar_senal_riesgo
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(
    texto=st.text(max_size=200),
    historial=st.lists(st.text(max_size=100), max_size=5),
)
def test_contrato_detectar_senal_riesgo(texto, historial):
    """
    Propiedad 5: La tool siempre devuelve exactamente nivel y frases_detectadas
    con los tipos y valores correctos.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop5.db")
        inicializar_db(ruta)
        os.environ["DB_PATH"] = ruta
        uid = db_models.crear_usuario("PropUser5", ruta_db=ruta)

        from agent.tools import detectar_senal_riesgo

        resultado = detectar_senal_riesgo(uid, texto, historial)

        assert isinstance(resultado, dict), "Debe devolver un dict"
        assert "nivel" in resultado, "Debe tener clave 'nivel'"
        assert "frases_detectadas" in resultado, "Debe tener clave 'frases_detectadas'"
        assert resultado["nivel"] in ("bajo", "medio", "alto"), (
            f"nivel debe ser bajo/medio/alto, obtuvo: {resultado['nivel']}"
        )
        assert isinstance(resultado["frases_detectadas"], list), (
            "frases_detectadas debe ser lista"
        )
        assert all(isinstance(f, str) for f in resultado["frases_detectadas"]), (
            "Cada frase detectada debe ser str"
        )


# ---------------------------------------------------------------------------
# Tests unitarios: sugerir_pausa
# ---------------------------------------------------------------------------

class TestSugerirPausa:
    def test_devuelve_entre_3_y_5(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import sugerir_pausa
        uid, _ = usuario
        resultado = sugerir_pausa(uid, [])
        sugs = resultado.get("sugerencias", [])
        assert 3 <= len(sugs) <= 5

    def test_no_mas_de_2_repetidas(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import sugerir_pausa, _POOL_SUGERENCIAS
        uid, _ = usuario
        previas = _POOL_SUGERENCIAS[:5]
        resultado = sugerir_pausa(uid, previas)
        sugs = resultado.get("sugerencias", [])
        repetidas = sum(1 for s in sugs if s in set(previas))
        assert repetidas <= 2

    def test_cada_sugerencia_max_15_palabras(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import sugerir_pausa
        uid, _ = usuario
        resultado = sugerir_pausa(uid, [])
        for s in resultado.get("sugerencias", []):
            palabras = len(s.split())
            assert palabras <= 15, f"Sugerencia demasiado larga ({palabras} palabras): '{s}'"


# ---------------------------------------------------------------------------
# Propiedad 7: Contrato de tamaño y contenido de sugerir_pausa
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=None)
@given(previas=st.lists(st.text(max_size=80), max_size=5))
def test_contrato_sugerir_pausa(previas):
    """
    Propiedad 7: sugerir_pausa debe devolver entre 3 y 5 sugerencias,
    cada una de ≤15 palabras, y no más de 2 coincidencias con las previas.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop7.db")
        inicializar_db(ruta)
        os.environ["DB_PATH"] = ruta
        uid = db_models.crear_usuario("PropUser7", ruta_db=ruta)

        from agent.tools import sugerir_pausa

        resultado = sugerir_pausa(uid, previas)
        sugs = resultado.get("sugerencias", [])

        assert 3 <= len(sugs) <= 5, f"Se esperaban 3–5 sugerencias, hay {len(sugs)}"
        for s in sugs:
            assert len(s.split()) <= 15, f"Sugerencia excede 15 palabras: '{s}'"
        repetidas = sum(1 for s in sugs if s in set(previas))
        assert repetidas <= 2, f"Más de 2 sugerencias repetidas: {repetidas}"


# ---------------------------------------------------------------------------
# Tests unitarios: explicar_tema
# ---------------------------------------------------------------------------

class TestExplicarTema:
    def test_tema_conocido_basico(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import explicar_tema
        uid, _ = usuario
        resultado = explicar_tema(uid, "tensión arterial", "básico")
        assert resultado.get("ok") is True
        assert resultado.get("explicacion") is not None
        assert len(resultado["explicacion"].split()) <= 200

    def test_tema_conocido_intermedio(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import explicar_tema
        uid, _ = usuario
        resultado = explicar_tema(uid, "diabetes", "intermedio")
        assert resultado.get("ok") is True

    def test_tema_desconocido_devuelve_fuente(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import explicar_tema
        uid, _ = usuario
        resultado = explicar_tema(uid, "mecánica cuántica", "básico")
        assert resultado.get("ok") is False
        assert resultado.get("fuente_sugerida") is not None

    def test_tema_vacio_devuelve_fuente(self, db_path, usuario, monkeypatch):
        _set_db(monkeypatch, db_path)
        from agent.tools import explicar_tema
        uid, _ = usuario
        resultado = explicar_tema(uid, "", "básico")
        assert resultado.get("ok") is False


# ---------------------------------------------------------------------------
# Propiedad 8: Contrato de longitud y nivel de explicar_tema
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    tema=st.text(min_size=1, max_size=200),
    nivel=st.sampled_from(["básico", "intermedio"]),
)
def test_contrato_explicar_tema(tema, nivel):
    """
    Propiedad 8: La explicación tiene ≤200 palabras o se devuelve fuente_sugerida.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        ruta = os.path.join(tmpdir, "prop8.db")
        inicializar_db(ruta)
        os.environ["DB_PATH"] = ruta
        uid = db_models.crear_usuario("PropUser8", ruta_db=ruta)

        from agent.tools import explicar_tema

        resultado = explicar_tema(uid, tema, nivel)

        assert isinstance(resultado, dict), "Debe devolver un dict"

        if "error" in resultado:
            assert isinstance(resultado["error"], str)
        elif resultado.get("ok") is True:
            explicacion = resultado.get("explicacion", "")
            if explicacion:
                palabras = len(explicacion.split())
                assert palabras <= 200, (
                    f"Explicación excede 200 palabras: {palabras}"
                )
        else:
            assert resultado.get("fuente_sugerida") is not None or resultado.get("ok") is False


# ---------------------------------------------------------------------------
# Propiedad 9: Captura de errores en todas las Tools
# ---------------------------------------------------------------------------

@settings(max_examples=20)
@given(st.sampled_from(["registrar_habito", "obtener_resumen_habitos",
                         "detectar_senal_riesgo", "sugerir_pausa", "explicar_tema"]))
def test_captura_errores_todas_las_tools(nombre_tool):
    """
    Propiedad 9: Ninguna Tool propaga excepciones no controladas.
    Siempre devuelven un dict, independientemente de los argumentos recibidos.
    """
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        ruta = os.path.join(tmpdir, "prop9.db")
        # NO inicializamos la DB para tools que la necesitan (registrar_habito, sugerir_pausa, explicar_tema)
        os.environ["DB_PATH"] = ruta

        import agent.tools as tools_mod
        tool_fn = getattr(tools_mod, nombre_tool)

        try:
            if nombre_tool == "registrar_habito":
                # Con categoría inválida y valor negativo, debe rechazar con ok=False, sin excepción
                resultado = tool_fn(-1, "categoría_invalida", -999.0, "")
                assert isinstance(resultado, dict), f"{nombre_tool} debe devolver dict"
                # Con args inválidos debe dar ok=False o error
                assert "error" in resultado or resultado.get("ok") is False

            elif nombre_tool == "obtener_resumen_habitos":
                # Con DB sin inicializar, puede devolver ok=True/{} o error — nunca excepción
                resultado = tool_fn(-1, 7)
                assert isinstance(resultado, dict), f"{nombre_tool} debe devolver dict"

            elif nombre_tool == "detectar_senal_riesgo":
                # Siempre devuelve nivel y frases_detectadas, nunca excepción
                resultado = tool_fn(-1, "texto", [])
                assert isinstance(resultado, dict), f"{nombre_tool} debe devolver dict"
                assert "nivel" in resultado
                assert "frases_detectadas" in resultado

            elif nombre_tool == "sugerir_pausa":
                # Devuelve sugerencias o _fallback, nunca excepción
                resultado = tool_fn(-1, [])
                assert isinstance(resultado, dict), f"{nombre_tool} debe devolver dict"
                assert "sugerencias" in resultado or "error" in resultado

            elif nombre_tool == "explicar_tema":
                # Con tema vacío, devuelve ok=False + fuente_sugerida, sin excepción
                resultado = tool_fn(-1, "", "nivel_invalido")
                assert isinstance(resultado, dict), f"{nombre_tool} debe devolver dict"

        except Exception as e:
            pytest.fail(
                f"{nombre_tool} propagó una excepción cuando no debería: {type(e).__name__}: {e}"
            )


# ---------------------------------------------------------------------------
# Propiedad 6: Persistencia de flag de derivación ante riesgo alto
# ---------------------------------------------------------------------------

def test_flag_derivacion_persiste_ante_riesgo_alto(db_path, usuario, monkeypatch):
    """
    Propiedad 6: Cuando detectar_senal_riesgo devuelve 'alto', el flag debe
    poder persistirse antes de que la sesión termine.
    """
    _set_db(monkeypatch, db_path)
    from agent.tools import detectar_senal_riesgo
    uid, sid = usuario

    resultado = detectar_senal_riesgo(
        uid, "no quiero vivir, quiero hacerme daño", []
    )
    assert resultado["nivel"] == "alto"

    # Persistir el flag (como haría MaxAgent)
    db_models.insertar_flag_derivacion(
        usuario_id=uid,
        nivel_riesgo=resultado["nivel"],
        frases_detectadas=resultado["frases_detectadas"],
        accion_tomada="Derivación indicada al usuario en el turno actual",
        sesion_id=sid,
        ruta_db=db_path,
    )

    assert db_models.tiene_flag_derivacion_activo(uid, sid, ruta_db=db_path) is True
