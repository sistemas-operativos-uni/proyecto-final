"""Pruebas del adaptador del Módulo 1 al contrato común (Fase 7).

`ModuloProcesos` implementa `ModuloSimulacion`: recibe un `SimulationConfig` y
devuelve un `ModuleResult` con los eventos y las métricas de planificación.
Un problema del escenario no lanza una excepción ni se pierde: queda en
`ModuleResult.errores` y en el estado.
"""

import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

from core.contratos import ModuloSimulacion
from core.modelos import (
    COMPLETADO,
    COMPLETADO_CON_ERRORES,
    FALLIDO,
    Evento,
    ModuleResult,
    SimulationConfig,
)
from modulo1_procesos.py.adaptador import ModuloProcesos
from modulo1_procesos.py.metricas_planificacion import comparar_algoritmos
from modulo1_procesos.py.planificador import comparar

RAIZ = Path(__file__).resolve().parent.parent
LOTE_PEQUENO = RAIZ / "escenarios" / "lote_pequeno.csv"
LOTE_GRANDE = RAIZ / "escenarios" / "lote_grande.csv"
CABECERA = "id,llegada,rafaga,prioridad,memoria_kb,cursos\n"
NOMBRES = ["FCFS", "SJF", "PRIORIDAD", "RR(q=2)"]


def ejecutar(**campos):
    campos.setdefault("escenario", LOTE_PEQUENO)
    return ModuloProcesos().ejecutar(SimulationConfig(**campos))


def escribir_csv(tmp_path, filas, nombre="escenario.csv"):
    ruta = tmp_path / nombre
    ruta.write_text(CABECERA + "".join(f + "\n" for f in filas), encoding="utf-8")
    return ruta


# --- Contrato ---------------------------------------------------------------


def test_cumple_el_contrato_de_modulo_de_simulacion():
    modulo = ModuloProcesos()
    assert isinstance(modulo, ModuloSimulacion)
    assert modulo.nombre == "procesos"


def test_devuelve_un_module_result_completado_sin_errores():
    r = ejecutar()
    assert isinstance(r, ModuleResult)
    assert (r.modulo, r.estado, r.errores) == ("procesos", COMPLETADO, ())


def test_ejecutar_dos_veces_da_el_mismo_resultado():
    assert ejecutar() == ejecutar()


def test_el_adaptador_no_imprime_nada(capsys):
    ejecutar()
    ejecutar(escenario=Path("no_existe.csv"))
    capturado = capsys.readouterr()
    assert capturado.out == "" and capturado.err == ""  # la presentación es de la CLI


def test_sin_escenario_usa_lote_pequeno():
    r = ModuloProcesos().ejecutar(SimulationConfig())
    assert r.estado == COMPLETADO
    assert r.metricas["escenario"] == "lote_pequeno.csv"


# --- Métricas ---------------------------------------------------------------


def test_las_metricas_incluyen_un_bloque_por_algoritmo_en_orden():
    m = ejecutar().metricas
    assert m["escenario"] == "lote_pequeno.csv"
    assert m["procesos"] == 4
    assert list(m["algoritmos"]) == NOMBRES


def test_las_metricas_coinciden_con_el_oraculo_de_lote_pequeno():
    algoritmos = ejecutar().metricas["algoritmos"]
    assert [algoritmos[n]["espera_media"] for n in NOMBRES] == [5.25, 3.75, 4.0, 7.0]
    assert [algoritmos[n]["retorno_medio"] for n in NOMBRES] == [9.5, 8.0, 8.25, 11.25]
    assert [algoritmos[n]["respuesta_media"] for n in NOMBRES] == [5.25, 3.75, 4.0, 1.75]
    assert [algoritmos[n]["cambios_contexto"] for n in NOMBRES] == [3, 3, 3, 8]
    assert algoritmos["FCFS"]["utilizacion_cpu"] == 100.0


def test_las_metricas_son_las_de_metricas_planificacion_sin_recalcular():
    esperado = {f["algoritmo"]: f for f in comparar_algoritmos(_procesos(LOTE_PEQUENO)).filas()}
    assert ejecutar().metricas["algoritmos"] == esperado


def test_el_mejor_algoritmo_aparece_si_hay_mas_de_uno():
    assert ejecutar().metricas["mejor"] == {"espera_media": "SJF", "respuesta_media": "RR(q=2)"}


def test_un_solo_algoritmo_no_tiene_mejor():
    m = ejecutar(algoritmo="sjf").metricas
    assert list(m["algoritmos"]) == ["SJF"]
    assert "mejor" not in m


def test_el_quantum_y_el_coste_de_cambio_llegan_a_los_algoritmos():
    m = ejecutar(quantum=3, cambio_contexto=1).metricas["algoritmos"]
    assert "RR(q=3)" in m
    assert m["FCFS"]["tiempo_total"] == 20 and m["FCFS"]["utilizacion_cpu"] == 85.0


def test_otro_escenario():
    m = ejecutar(escenario=LOTE_GRANDE).metricas
    assert (m["escenario"], m["procesos"]) == ("lote_grande.csv", 10)


# --- Eventos ----------------------------------------------------------------


def test_los_eventos_llevan_el_algoritmo_que_los_produjo():
    r = ejecutar()
    assert r.eventos and all(isinstance(e, Evento) for e in r.eventos)
    assert {e.datos["algoritmo"] for e in r.eventos} == set(NOMBRES)
    assert {e.modulo for e in r.eventos} == {"procesos"}


def test_los_eventos_de_cada_algoritmo_son_los_de_su_simulacion():
    r = ejecutar()
    for nombre, esperado in zip(NOMBRES, comparar(_procesos(LOTE_PEQUENO)).values()):
        propios = [e for e in r.eventos if e.datos["algoritmo"] == nombre]
        sin_etiqueta = [Evento(e.instante, e.modulo, e.entidad, e.accion, {k: v for k, v in e.datos.items() if k != "algoritmo"}) for e in propios]
        assert tuple(sin_etiqueta) == esperado.eventos


def test_los_eventos_de_cada_algoritmo_quedan_juntos_en_el_orden_del_registro():
    # Cada algoritmo es una simulación aparte con su propio reloj: no se mezclan.
    etiquetas = [e.datos["algoritmo"] for e in ejecutar().eventos]
    colapsadas = [e for i, e in enumerate(etiquetas) if i == 0 or etiquetas[i - 1] != e]
    assert colapsadas == NOMBRES


def test_un_solo_algoritmo_solo_emite_sus_eventos():
    r = ejecutar(algoritmo="FCFS")
    assert {e.datos["algoritmo"] for e in r.eventos} == {"FCFS"}
    assert len(r.eventos) == 12


# --- Fallos del escenario ---------------------------------------------------


def test_un_archivo_inexistente_deja_un_resultado_fallido_con_el_motivo(tmp_path):
    r = ejecutar(escenario=tmp_path / "no_existe.csv")
    assert r.estado == FALLIDO
    assert len(r.errores) == 1 and "no_existe.csv" in r.errores[0]
    assert r.eventos == ()
    assert r.metricas == {"escenario": "no_existe.csv"}


def test_una_cabecera_sin_columnas_obligatorias_es_fallida(tmp_path):
    ruta = tmp_path / "malo.csv"
    ruta.write_text("id,llegada\nP001,0\n", encoding="utf-8")
    r = ejecutar(escenario=ruta)
    assert r.estado == FALLIDO and "rafaga" in r.errores[0]


def test_una_carpeta_en_lugar_de_archivo_es_fallida(tmp_path):
    r = ejecutar(escenario=tmp_path)
    assert r.estado == FALLIDO and r.errores


def test_una_fila_invalida_es_un_error_recuperable_que_no_detiene_la_simulacion(tmp_path):
    ruta = escribir_csv(
        tmp_path,
        [
            "P001,0,5,2,128,SO101",
            "P002,1,0,1,96,SO101",  # línea 3: ráfaga 0
            "P003,2,7,3,160,ARQ110",
            "P004,4,2,2,64,SO101",
        ],
    )
    r = ejecutar(escenario=ruta)
    assert r.estado == COMPLETADO_CON_ERRORES
    assert len(r.errores) == 1 and r.errores[0].startswith("línea 3")
    assert r.metricas["procesos"] == 3
    assert {e.entidad for e in r.eventos if e.entidad != "CPU"} == {"P001", "P003", "P004"}
    # P001 0-5, P003 5-12, P004 12-14: esperas 0, 3 y 8.
    assert r.metricas["algoritmos"]["FCFS"]["espera_media"] == pytest.approx(11 / 3)


def test_con_todas_las_filas_invalidas_el_resultado_es_fallido_y_conserva_los_errores(tmp_path):
    ruta = escribir_csv(tmp_path, ["P001,0,0,1,64,", "P002,0,0,1,64,"])
    r = ejecutar(escenario=ruta)
    assert r.estado == FALLIDO
    assert r.errores[0].startswith("línea 2") and r.errores[1].startswith("línea 3")
    assert "ningún proceso válido" in r.errores[-1]
    assert r.eventos == ()


def test_un_escenario_solo_con_cabecera_es_fallido(tmp_path):
    r = ejecutar(escenario=escribir_csv(tmp_path, []))
    assert r.estado == FALLIDO and "no tiene procesos" in r.errores[0]


def test_un_algoritmo_desconocido_es_fallido_y_lista_los_validos():
    r = ejecutar(algoritmo="XYZ")
    assert r.estado == FALLIDO
    assert "XYZ" in r.errores[0] and "FCFS, SJF, PRIORIDAD, RR" in r.errores[0]
    assert r.eventos == ()


# --- Exportación ------------------------------------------------------------


requiere_matplotlib = pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="falta matplotlib")


@requiere_matplotlib
def test_exportar_escribe_csv_json_y_grafico_e_informa_las_rutas(tmp_path):
    r = ejecutar(exportar=True, directorio_resultados=tmp_path)
    assert r.estado == COMPLETADO
    csv_, json_ = tmp_path / "procesos_lote_pequeno.csv", tmp_path / "procesos_lote_pequeno.json"
    png = tmp_path / "procesos_lote_pequeno.png"
    assert csv_.is_file() and json_.is_file() and png.read_bytes().startswith(b"\x89PNG")
    assert r.metricas["exportado"] == {"csv": str(csv_), "json": str(json_), "grafico": str(png)}


def test_si_el_grafico_falla_se_conservan_el_csv_y_el_json(tmp_path, monkeypatch):
    def sin_matplotlib(*_):
        raise ImportError("No module named 'matplotlib'")

    monkeypatch.setattr("modulo1_procesos.py.adaptador.graficar_comparacion", sin_matplotlib)
    r = ejecutar(exportar=True, directorio_resultados=tmp_path)
    assert r.estado == COMPLETADO_CON_ERRORES
    assert len(r.errores) == 1 and r.errores[0].startswith("no se pudo graficar")
    csv_, json_ = tmp_path / "procesos_lote_pequeno.csv", tmp_path / "procesos_lote_pequeno.json"
    assert csv_.is_file() and json_.is_file()
    assert r.metricas["exportado"] == {"csv": str(csv_), "json": str(json_)}


def test_sin_exportar_no_se_escribe_nada(tmp_path):
    r = ejecutar(directorio_resultados=tmp_path)
    assert list(tmp_path.iterdir()) == [] and "exportado" not in r.metricas


def test_exportar_con_un_solo_algoritmo_es_fallido(tmp_path):
    r = ejecutar(algoritmo="FCFS", exportar=True, directorio_resultados=tmp_path)
    assert r.estado == FALLIDO and "todos" in r.errores[0]
    assert list(tmp_path.iterdir()) == []


def test_si_la_exportacion_falla_la_simulacion_se_conserva(tmp_path):
    archivo = tmp_path / "no_es_carpeta"
    archivo.write_text("x", encoding="utf-8")
    r = ejecutar(exportar=True, directorio_resultados=archivo)
    assert r.estado == COMPLETADO_CON_ERRORES
    assert "no se pudo exportar" in r.errores[0]
    assert list(r.metricas["algoritmos"]) == NOMBRES and "exportado" not in r.metricas


def test_un_error_de_fila_y_uno_de_exportacion_se_acumulan(tmp_path):
    ruta = escribir_csv(tmp_path, ["P001,0,5,2,128,SO101", "P002,1,0,1,96,SO101"])
    archivo = tmp_path / "x"
    archivo.write_text("x", encoding="utf-8")
    r = ejecutar(escenario=ruta, exportar=True, directorio_resultados=archivo)
    assert r.estado == COMPLETADO_CON_ERRORES and len(r.errores) == 2


# --- Aislamiento: el Módulo 1 no depende de los Módulos 2 a 7 ----------------

DIRECTORIO_PY = RAIZ / "modulo1_procesos" / "py"
OTROS_MODULOS = re.compile(r"^modulo[2-7]_")


def _raices_importadas(archivo: Path):
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            yield from (a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            yield nodo.module.split(".")[0]  # también cubre `from ..modulo4_memoria import x`


def test_el_codigo_del_modulo_1_no_importa_modulo2_a_modulo7():
    archivos = sorted(DIRECTORIO_PY.glob("*.py"))
    assert len(archivos) >= 10  # la prueba no puede pasar por no encontrar nada
    infractores = [
        f"{a.name}: {raiz}" for a in archivos for raiz in _raices_importadas(a) if OTROS_MODULOS.match(raiz)
    ]
    assert infractores == []


def test_importar_el_modulo_1_no_carga_ningun_otro_modulo():
    # Las importaciones indirectas escapan al análisis del código fuente: se
    # comprueba en un proceso limpio, que no hereda los módulos de otras pruebas.
    codigo = (
        "import re, sys\n"
        "import modulo1_procesos.py.adaptador, modulo1_procesos.py.cli\n"
        "print(sorted(m for m in sys.modules if re.match(r'modulo[2-7]_', m)))\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "[]"


def _procesos(ruta):
    from core.cargador_escenarios import cargar_procesos

    return cargar_procesos(ruta)
