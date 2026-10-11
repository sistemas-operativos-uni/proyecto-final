"""Pruebas del núcleo compartido: modelos y contratos (Fase 0 del Módulo 1)."""

import ast
import dataclasses
from pathlib import Path

import pytest

from core.contratos import ModuloSimulacion
from core.modelos import (
    COMPLETADO,
    COMPLETADO_CON_ERRORES,
    FALLIDO,
    Evento,
    ModuleResult,
    Proceso,
    SimulationConfig,
)

RAIZ_CORE = Path(__file__).resolve().parent.parent / "core"


def proceso_valido(**cambios):
    base = dict(
        id="P001",
        llegada=0,
        rafaga=5,
        prioridad=2,
        memoria_kb=128,
        cursos=("SO101", "BD202"),
    )
    base.update(cambios)
    return Proceso(**base)


# --- Proceso ---------------------------------------------------------------


def test_proceso_conserva_los_campos_del_csv():
    p = proceso_valido()
    assert (p.id, p.llegada, p.rafaga, p.prioridad, p.memoria_kb) == ("P001", 0, 5, 2, 128)
    assert p.cursos == ("SO101", "BD202")


def test_proceso_es_inmutable():
    p = proceso_valido()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.rafaga = 9


def test_proceso_convierte_lista_de_cursos_en_tupla():
    p = proceso_valido(cursos=["SO101"])
    assert p.cursos == ("SO101",)


def test_proceso_acepta_cursos_vacios():
    assert proceso_valido(cursos=()).cursos == ()


@pytest.mark.parametrize(
    "cambios",
    [
        {"id": ""},
        {"id": "   "},
        {"llegada": -1},
        {"rafaga": 0},
        {"rafaga": -3},
        {"prioridad": -1},
        {"memoria_kb": 0},
        {"llegada": 1.5},
        {"rafaga": "5"},
    ],
)
def test_proceso_invalido_lanza_value_error(cambios):
    with pytest.raises(ValueError):
        proceso_valido(**cambios)


# --- Evento ----------------------------------------------------------------


def test_evento_guarda_instante_modulo_entidad_accion_y_datos():
    e = Evento(instante=3, modulo="procesos", entidad="P001", accion="DESPACHO", datos={"espera": 0})
    assert (e.instante, e.modulo, e.entidad, e.accion) == (3, "procesos", "P001", "DESPACHO")
    assert e.datos == {"espera": 0}


def test_evento_sin_datos_usa_diccionario_propio():
    a = Evento(0, "procesos", "P001", "LLEGADA")
    b = Evento(0, "procesos", "P002", "LLEGADA")
    assert a.datos == {} and a.datos is not b.datos


def test_evento_rechaza_instante_negativo():
    with pytest.raises(ValueError):
        Evento(-1, "procesos", "P001", "LLEGADA")


@pytest.mark.parametrize("campo", ["modulo", "entidad", "accion"])
def test_evento_rechaza_textos_vacios(campo):
    campos = dict(instante=0, modulo="procesos", entidad="P001", accion="LLEGADA")
    campos[campo] = ""
    with pytest.raises(ValueError):
        Evento(**campos)


# --- SimulationConfig ------------------------------------------------------


def test_config_tiene_valores_por_defecto_documentados():
    c = SimulationConfig()
    assert c.escenario is None
    assert c.algoritmo == "todos"
    assert c.quantum == 2
    assert c.cambio_contexto == 0
    assert c.directorio_resultados == Path("resultados")
    assert c.exportar is False


def test_config_acepta_exportar_y_lo_rechaza_si_no_es_booleano():
    assert SimulationConfig(exportar=True).exportar is True
    for invalido in (1, "si", None):
        with pytest.raises(ValueError, match="exportar"):
            SimulationConfig(exportar=invalido)


def test_config_convierte_texto_a_ruta():
    c = SimulationConfig(escenario="escenarios/lote_pequeno.csv")
    assert c.escenario == Path("escenarios/lote_pequeno.csv")


@pytest.mark.parametrize("quantum", [0, -1])
def test_config_rechaza_quantum_no_positivo(quantum):
    with pytest.raises(ValueError):
        SimulationConfig(quantum=quantum)


def test_config_rechaza_cambio_de_contexto_negativo():
    with pytest.raises(ValueError):
        SimulationConfig(cambio_contexto=-1)


def test_config_es_inmutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        SimulationConfig().quantum = 5


# --- ModuleResult ----------------------------------------------------------


def evento_demo():
    return Evento(0, "procesos", "P001", "LLEGADA")


def test_resultado_completado_sin_errores():
    r = ModuleResult("procesos", COMPLETADO, [evento_demo()], {"espera_media": 5.25}, [])
    assert r.estado == "completado"
    assert r.eventos == (evento_demo(),)
    assert r.errores == ()
    assert r.metricas["espera_media"] == 5.25


def test_resultado_con_errores_recuperables():
    r = ModuleResult("procesos", COMPLETADO_CON_ERRORES, [], {}, ["fila 3: ráfaga inválida"])
    assert r.errores == ("fila 3: ráfaga inválida",)


def test_resultado_fallido_exige_errores():
    with pytest.raises(ValueError):
        ModuleResult("procesos", FALLIDO, [], {}, [])


def test_resultado_completado_no_admite_errores():
    with pytest.raises(ValueError):
        ModuleResult("procesos", COMPLETADO, [], {}, ["algo falló"])


def test_resultado_con_errores_exige_al_menos_uno():
    with pytest.raises(ValueError):
        ModuleResult("procesos", COMPLETADO_CON_ERRORES, [], {}, [])


def test_resultado_rechaza_estado_desconocido():
    with pytest.raises(ValueError):
        ModuleResult("procesos", "quizás", [], {}, [])


def test_estados_coinciden_con_los_del_modulo_4():
    # El Módulo 4 ya publica estos textos; cambiarlos rompería su adaptación.
    assert (COMPLETADO, COMPLETADO_CON_ERRORES) == ("completado", "completado_con_errores")


# --- Contrato de módulo ----------------------------------------------------


class ModuloFalso:
    nombre = "falso"

    def ejecutar(self, config):
        return ModuleResult(self.nombre, COMPLETADO, [], {}, [])


class SinEjecutar:
    nombre = "incompleto"


def test_un_modulo_con_nombre_y_ejecutar_cumple_el_contrato():
    modulo = ModuloFalso()
    assert isinstance(modulo, ModuloSimulacion)
    assert modulo.ejecutar(SimulationConfig()).estado == COMPLETADO


def test_un_modulo_sin_ejecutar_no_cumple_el_contrato():
    assert not isinstance(SinEjecutar(), ModuloSimulacion)


# --- Regla de dependencias -------------------------------------------------


def test_core_no_importa_modulos_concretos():
    # docs/arquitectura.md: core -X-> módulos concretos.
    infractores = []
    for archivo in RAIZ_CORE.glob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            else:
                continue
            infractores += [f"{archivo.name}: {n}" for n in nombres if n.startswith("modulo")]
    assert infractores == []
