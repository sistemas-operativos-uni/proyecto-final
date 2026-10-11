"""Pruebas de las métricas de planificación (Fase 6 del Módulo 1).

Las métricas se derivan SOLO de la lista de eventos. Por eso la primera
mitad de este archivo alimenta el cálculo con eventos escritos a mano, sin
pasar por ningún algoritmo: si el cálculo mirara otra cosa, esas pruebas
fallarían. La segunda mitad cruza el resultado con los cuatro algoritmos.

Definiciones fijadas aquí:
  - espera: tiempo total en estado LISTO. retorno: fin - llegada.
    respuesta: primer despacho - llegada.
  - utilización de CPU: tiempo ejecutando procesos / tiempo total, en %.
    El tiempo ocioso y el de cambios de contexto cuentan como no utilizado.
  - throughput: procesos terminados por unidad de tiempo.
  - tiempo total: instante del último evento (la corrida empieza en 0).
"""

import csv
import dataclasses
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core.cargador_escenarios import cargar_procesos
from core.modelos import Evento, Proceso, SimulationConfig
from modulo1_procesos.py.cli import main
from modulo1_procesos.py.diagrama import tabla_comparativa
from modulo1_procesos.py.metricas_planificacion import (
    COLUMNAS_COMPARACION,
    ComparacionAlgoritmos,
    MetricasPlanificacion,
    MetricasProceso,
    calcular_metricas,
    comparar_algoritmos,
    exportar_comparacion,
    metricas_de,
)
from modulo1_procesos.py.planificador import planificar

RAIZ = Path(__file__).resolve().parent.parent
ALGORITMOS = ["FCFS", "SJF", "PRIORIDAD", "RR"]


def P(id, llegada, rafaga, prio=1):
    return Proceso(id, llegada, rafaga, prio, 64, ())


def lote_pequeno():
    return cargar_procesos(RAIZ / "escenarios" / "lote_pequeno.csv")


def lote_grande():
    return cargar_procesos(RAIZ / "escenarios" / "lote_grande.csv")


def por_pid(metricas, campo):
    return {p.pid: getattr(p, campo) for p in metricas.procesos}


# --- Constructores de eventos escritos a mano --------------------------------


def transicion(instante, pid, desde, hacia):
    return Evento(instante, "procesos", pid, "TRANSICION", {"desde": desde, "hacia": hacia, "restante": 0})


def ocio(instante, hasta):
    return Evento(instante, "procesos", "CPU", "OCIOSA", {"hasta": hasta})


def cambio(instante, de, a, costo):
    return Evento(instante, "procesos", "CPU", "CAMBIO_CONTEXTO", {"de": de, "a": a, "costo": costo})


def expropiacion(instante, pid, restante, cola):
    return Evento(instante, "procesos", pid, "EXPROPIACION", {"restante": restante, "cola": tuple(cola)})


# ===========================================================================
# Derivación desde eventos (sin algoritmos)
# ===========================================================================


def test_un_proceso_expropiado_se_mide_solo_con_sus_eventos():
    eventos = [
        transicion(0, "P001", "NUEVO", "LISTO"),
        transicion(2, "P001", "LISTO", "EJECUCION"),
        transicion(4, "P001", "EJECUCION", "LISTO"),
        expropiacion(4, "P001", 2, ["P001"]),  # evento informativo: no altera las cuentas
        transicion(6, "P001", "LISTO", "EJECUCION"),
        transicion(8, "P001", "EJECUCION", "TERMINADO"),
    ]
    m = calcular_metricas("X", eventos)
    (p,) = m.procesos
    assert (p.pid, p.llegada, p.primer_despacho, p.fin) == ("P001", 0, 2, 8)
    assert p.rafaga == 4  # 2 + 2 unidades en CPU
    assert p.espera == 4  # (0 a 2) + (4 a 6) en la cola de listos
    assert (p.retorno, p.respuesta) == (8, 2)
    assert m.tiempo_total == 8


def test_los_cambios_de_contexto_se_cuentan_entre_procesos_distintos_y_el_hueco_los_reinicia():
    eventos = [
        transicion(0, "A", "NUEVO", "LISTO"),
        transicion(0, "B", "NUEVO", "LISTO"),
        transicion(0, "A", "LISTO", "EJECUCION"),
        transicion(1, "A", "EJECUCION", "LISTO"),
        transicion(1, "A", "LISTO", "EJECUCION"),  # sigue A: no es un cambio
        transicion(2, "A", "EJECUCION", "TERMINADO"),
        transicion(2, "B", "LISTO", "EJECUCION"),  # A -> B: cambio 1
        transicion(4, "B", "EJECUCION", "TERMINADO"),
        ocio(4, 6),
        transicion(6, "C", "NUEVO", "LISTO"),
        transicion(6, "C", "LISTO", "EJECUCION"),  # después del hueco: no cuenta
        transicion(7, "C", "EJECUCION", "TERMINADO"),
    ]
    m = calcular_metricas("X", eventos)
    assert m.cambios_contexto == 1
    assert (m.tiempo_total, m.tiempo_cpu, m.tiempo_ocioso, m.tiempo_cambios) == (7, 5, 2, 0)
    assert m.utilizacion_cpu == pytest.approx(5 / 7 * 100)
    assert m.throughput == pytest.approx(3 / 7)


def test_el_tiempo_de_cambios_sale_de_los_eventos_de_cambio_de_contexto():
    eventos = [
        transicion(0, "A", "NUEVO", "LISTO"),
        transicion(0, "B", "NUEVO", "LISTO"),
        transicion(0, "A", "LISTO", "EJECUCION"),
        transicion(2, "A", "EJECUCION", "TERMINADO"),
        cambio(2, "A", "B", 3),
        transicion(5, "B", "LISTO", "EJECUCION"),
        transicion(7, "B", "EJECUCION", "TERMINADO"),
    ]
    m = calcular_metricas("X", eventos)
    assert (m.tiempo_total, m.tiempo_cpu, m.tiempo_cambios) == (7, 4, 3)
    assert m.cambios_contexto == 1
    assert por_pid(m, "espera")["B"] == 5  # esperó también durante el cambio


def test_sin_eventos_no_hay_metricas_que_promediar():
    m = calcular_metricas("FCFS", [])
    assert m.algoritmo == "FCFS" and m.procesos == ()
    assert (m.espera_media, m.retorno_medio, m.respuesta_media) == (None, None, None)
    assert (m.utilizacion_cpu, m.throughput) == (None, None)
    assert (m.tiempo_total, m.cambios_contexto) == (0, 0)


def test_un_despacho_de_un_proceso_que_nunca_llego_es_un_error():
    with pytest.raises(ValueError, match="P009"):
        calcular_metricas("X", [transicion(1, "P009", "LISTO", "EJECUCION")])


def test_un_proceso_que_no_termino_es_un_error():
    eventos = [transicion(0, "P001", "NUEVO", "LISTO"), transicion(1, "P001", "LISTO", "EJECUCION")]
    with pytest.raises(ValueError, match="P001"):
        calcular_metricas("X", eventos)


def test_las_metricas_son_inmutables():
    m = calcular_metricas("X", [])
    assert isinstance(m, MetricasPlanificacion)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.algoritmo = "otro"
    p = MetricasProceso("P1", 0, 0, 1, 1, 0, 1, 0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.espera = 5


# ===========================================================================
# Oráculo de lote_pequeno.csv con los cuatro algoritmos
# ===========================================================================


def metricas_algoritmo(nombre, procesos=None, **config):
    resultado = planificar(nombre, procesos or lote_pequeno(), SimulationConfig(**config))
    return metricas_de(resultado)


@pytest.mark.parametrize(
    "nombre, espera, retorno, respuesta",
    [
        ("FCFS", {"P001": 0, "P002": 4, "P003": 6, "P004": 11}, {"P001": 5, "P002": 7, "P003": 13, "P004": 13},
         {"P001": 0, "P002": 4, "P003": 6, "P004": 11}),
        ("SJF", {"P001": 0, "P002": 6, "P003": 8, "P004": 1}, {"P001": 5, "P002": 9, "P003": 15, "P004": 3},
         {"P001": 0, "P002": 6, "P003": 8, "P004": 1}),
        ("PRIORIDAD", {"P001": 0, "P002": 4, "P003": 8, "P004": 4}, {"P001": 5, "P002": 7, "P003": 15, "P004": 6},
         {"P001": 0, "P002": 4, "P003": 8, "P004": 4}),
        ("RR", {"P001": 9, "P002": 7, "P003": 8, "P004": 4}, {"P001": 14, "P002": 10, "P003": 15, "P004": 6},
         {"P001": 0, "P002": 1, "P003": 2, "P004": 4}),
    ],
)  # fmt: skip
def test_oraculo_por_proceso(nombre, espera, retorno, respuesta):
    m = metricas_algoritmo(nombre)
    assert por_pid(m, "espera") == espera
    assert por_pid(m, "retorno") == retorno
    assert por_pid(m, "respuesta") == respuesta


@pytest.mark.parametrize(
    "nombre, espera_media, retorno_medio, respuesta_media, cambios",
    [
        ("FCFS", 5.25, 9.5, 5.25, 3),
        ("SJF", 3.75, 8.0, 3.75, 3),
        ("PRIORIDAD", 4.0, 8.25, 4.0, 3),
        ("RR", 7.0, 11.25, 1.75, 8),
    ],
)
def test_oraculo_de_las_medias_y_los_cambios_de_contexto(nombre, espera_media, retorno_medio, respuesta_media, cambios):
    m = metricas_algoritmo(nombre)
    assert m.espera_media == espera_media
    assert m.retorno_medio == retorno_medio
    assert m.respuesta_media == respuesta_media
    assert m.cambios_contexto == cambios


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_lote_pequeno_mantiene_la_cpu_al_100_por_ciento(nombre):
    m = metricas_algoritmo(nombre)
    assert (m.tiempo_total, m.tiempo_cpu, m.tiempo_ocioso, m.tiempo_cambios) == (17, 17, 0, 0)
    assert m.utilizacion_cpu == 100.0
    assert m.throughput == pytest.approx(4 / 17)


def test_rr_con_quantum_1_oraculo():
    m = metricas_algoritmo("RR", quantum=1)
    assert (m.espera_media, m.respuesta_media, m.cambios_contexto) == (6.5, 0.75, 13)


# --- Utilización con tiempo ocioso y con coste de cambio ---------------------


def test_cpu_ociosa_entre_procesos_baja_la_utilizacion():
    m = metricas_algoritmo("FCFS", [P("P001", 0, 2), P("P002", 5, 1)])
    assert (m.tiempo_total, m.tiempo_cpu, m.tiempo_ocioso) == (6, 3, 3)
    assert m.utilizacion_cpu == 50.0
    assert m.throughput == pytest.approx(2 / 6)


def test_el_ocio_inicial_cuenta_como_tiempo_total():
    m = metricas_algoritmo("SJF", [P("P001", 3, 4)])
    assert (m.tiempo_total, m.tiempo_ocioso) == (7, 3)
    assert m.utilizacion_cpu == pytest.approx(4 / 7 * 100)


def test_el_coste_de_cambio_de_contexto_baja_la_utilizacion():
    m = metricas_algoritmo("FCFS", cambio_contexto=1)
    assert (m.tiempo_total, m.tiempo_cpu, m.tiempo_cambios, m.cambios_contexto) == (20, 17, 3, 3)
    assert m.utilizacion_cpu == 85.0
    assert m.espera_media == 6.75


# ===========================================================================
# Coherencia con el resultado de cada algoritmo
# ===========================================================================

ESCENARIOS = {
    "pequeno": lote_pequeno,
    "grande": lote_grande,
    "con_huecos": lambda: [P("P001", 3, 4), P("P002", 10, 2), P("P003", 10, 3, 2), P("P004", 30, 1)],
}


@pytest.mark.parametrize("coste", [0, 1, 3])
@pytest.mark.parametrize("escenario", list(ESCENARIOS))
@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_las_metricas_de_los_eventos_coinciden_con_el_resultado_del_algoritmo(nombre, escenario, coste):
    procesos = ESCENARIOS[escenario]()
    resultado = planificar(nombre, procesos, SimulationConfig(cambio_contexto=coste))
    m = metricas_de(resultado)

    assert [p.pid for p in m.procesos] == [p.pid for p in resultado.procesos]
    for derivado, esperado in zip(m.procesos, resultado.procesos):
        assert derivado.llegada == esperado.llegada
        assert derivado.rafaga == esperado.rafaga
        assert derivado.primer_despacho == esperado.inicio
        assert derivado.fin == esperado.fin
        assert derivado.espera == esperado.espera
        assert derivado.retorno == esperado.retorno
        assert derivado.respuesta == esperado.respuesta
    assert m.espera_media == resultado.espera_media
    assert m.retorno_medio == resultado.retorno_medio
    assert m.cambios_contexto == resultado.cambios_contexto


@pytest.mark.parametrize("coste", [0, 1, 3])
@pytest.mark.parametrize("escenario", list(ESCENARIOS))
@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_el_tiempo_total_se_reparte_entre_cpu_ocio_y_cambios(nombre, escenario, coste):
    m = metricas_de(planificar(nombre, ESCENARIOS[escenario](), SimulationConfig(cambio_contexto=coste)))
    assert m.tiempo_total == m.tiempo_cpu + m.tiempo_ocioso + m.tiempo_cambios
    assert m.tiempo_cpu == sum(p.rafaga for p in m.procesos)
    assert m.tiempo_cambios == coste * m.cambios_contexto
    assert 0 < m.utilizacion_cpu <= 100
    assert m.throughput == pytest.approx(len(m.procesos) / m.tiempo_total)
    for p in m.procesos:
        assert p.retorno == p.espera + p.rafaga
        assert 0 <= p.respuesta <= p.espera


# ===========================================================================
# Comparación de algoritmos
# ===========================================================================


def test_comparar_algoritmos_devuelve_un_resultado_por_algoritmo_en_orden():
    c = comparar_algoritmos(lote_pequeno())
    assert isinstance(c, ComparacionAlgoritmos)
    assert [m.algoritmo for m in c.metricas] == ["FCFS", "SJF", "PRIORIDAD", "RR(q=2)"]
    assert c.nombres == ("FCFS", "SJF", "PRIORIDAD", "RR(q=2)")


def test_todos_los_algoritmos_se_miden_sobre_el_mismo_escenario():
    c = comparar_algoritmos(lote_pequeno())
    pids = [tuple(p.pid for p in m.procesos) for m in c.metricas]
    assert len(set(pids)) == 1 and pids[0] == ("P001", "P002", "P003", "P004")
    assert {sum(p.rafaga for p in m.procesos) for m in c.metricas} == {17}


def test_comparar_acepta_un_generador_sin_agotarlo_en_el_primer_algoritmo():
    c = comparar_algoritmos(iter(lote_pequeno()))
    assert [len(m.procesos) for m in c.metricas] == [4, 4, 4, 4]


def test_comparar_respeta_la_configuracion():
    c = comparar_algoritmos(lote_pequeno(), SimulationConfig(quantum=3, cambio_contexto=1))
    assert c.nombres[-1] == "RR(q=3)"
    assert all(m.tiempo_cambios == m.cambios_contexto for m in c.metricas)


def test_mejor_algoritmo_segun_cada_metrica():
    c = comparar_algoritmos(lote_pequeno())
    assert c.mejor("espera_media") == "SJF"
    assert c.mejor("retorno_medio") == "SJF"
    assert c.mejor("respuesta_media") == "RR(q=2)"
    assert c.mejor("cambios_contexto") == "FCFS"  # empata con SJF y PRIORIDAD: gana el primero


def test_en_utilizacion_y_throughput_mejor_significa_mayor():
    base = calcular_metricas("A", [])
    a = dataclasses.replace(base, algoritmo="A", utilizacion_cpu=50.0, throughput=0.1, espera_media=2.0)
    b = dataclasses.replace(base, algoritmo="B", utilizacion_cpu=80.0, throughput=0.3, espera_media=9.0)
    c = dataclasses.replace(base, algoritmo="C", utilizacion_cpu=80.0, throughput=0.2, espera_media=9.0)
    comparacion = ComparacionAlgoritmos((a, b, c))
    assert comparacion.mejor("utilizacion_cpu") == "B"  # el mayor; B gana el empate con C por ir antes
    assert comparacion.mejor("throughput") == "B"
    assert comparacion.mejor("espera_media") == "A"  # en tiempos, el menor


def test_mejor_con_una_metrica_desconocida_lanza_value_error():
    with pytest.raises(ValueError, match="espera_media"):
        comparar_algoritmos(lote_pequeno()).mejor("inventada")


def test_comparar_una_lista_vacia_no_falla_y_no_tiene_mejor():
    c = comparar_algoritmos([])
    assert len(c.metricas) == 4
    assert c.mejor("espera_media") is None


def test_las_filas_de_la_comparacion_tienen_las_columnas_fijas():
    filas = comparar_algoritmos(lote_pequeno()).filas()
    assert COLUMNAS_COMPARACION == (
        "algoritmo", "espera_media", "retorno_medio", "respuesta_media",
        "utilizacion_cpu", "throughput", "cambios_contexto", "tiempo_total",
    )  # fmt: skip
    assert all(tuple(fila) == COLUMNAS_COMPARACION for fila in filas)
    assert filas[1]["algoritmo"] == "SJF" and filas[1]["espera_media"] == 3.75


# ===========================================================================
# Exportación a resultados/procesos_<escenario>.csv y .json
# ===========================================================================


def test_exportar_crea_los_dos_archivos_con_el_nombre_del_escenario(tmp_path):
    ruta_csv, ruta_json = exportar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno.csv", tmp_path)
    assert ruta_csv == tmp_path / "procesos_lote_pequeno.csv"
    assert ruta_json == tmp_path / "procesos_lote_pequeno.json"
    assert ruta_csv.is_file() and ruta_json.is_file()


def test_el_nombre_ignora_la_carpeta_y_la_extension_del_escenario(tmp_path):
    ruta_csv, _ = exportar_comparacion(comparar_algoritmos([]), "escenarios/lote_grande.csv", tmp_path)
    assert ruta_csv.name == "procesos_lote_grande.csv"


def test_el_csv_tiene_una_fila_por_algoritmo_con_las_columnas_fijas(tmp_path):
    ruta_csv, _ = exportar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno", tmp_path)
    with ruta_csv.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        filas = list(lector)
        assert tuple(lector.fieldnames) == COLUMNAS_COMPARACION
    assert [f["algoritmo"] for f in filas] == ["FCFS", "SJF", "PRIORIDAD", "RR(q=2)"]
    fcfs = filas[0]
    assert (fcfs["espera_media"], fcfs["retorno_medio"], fcfs["utilizacion_cpu"]) == ("5.25", "9.5", "100.0")
    assert fcfs["throughput"] == "0.2353"  # redondeado a 4 decimales
    assert (fcfs["cambios_contexto"], fcfs["tiempo_total"]) == ("3", "17")


def test_el_json_incluye_el_detalle_por_proceso(tmp_path):
    _, ruta_json = exportar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno.csv", tmp_path)
    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    assert datos["escenario"] == "lote_pequeno"
    assert [a["algoritmo"] for a in datos["algoritmos"]] == ["FCFS", "SJF", "PRIORIDAD", "RR(q=2)"]
    sjf = datos["algoritmos"][1]
    assert sjf["espera_media"] == 3.75 and sjf["cambios_contexto"] == 3
    p004 = next(p for p in sjf["procesos"] if p["pid"] == "P004")
    assert (p004["llegada"], p004["primer_despacho"], p004["fin"]) == (4, 5, 7)
    assert (p004["espera"], p004["retorno"], p004["respuesta"], p004["rafaga"]) == (1, 3, 1, 2)


def test_el_json_conserva_none_como_null_cuando_no_hay_procesos(tmp_path):
    _, ruta_json = exportar_comparacion(comparar_algoritmos([]), "vacio", tmp_path)
    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    assert datos["algoritmos"][0]["espera_media"] is None
    assert datos["algoritmos"][0]["procesos"] == []


def test_exportar_crea_los_directorios_que_falten(tmp_path):
    destino = tmp_path / "a" / "b"
    ruta_csv, _ = exportar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno", destino)
    assert ruta_csv.parent == destino and ruta_csv.is_file()


def test_exportar_dos_veces_da_el_mismo_contenido(tmp_path):
    comparacion = comparar_algoritmos(lote_pequeno())
    primero = [p.read_bytes() for p in exportar_comparacion(comparacion, "lote_pequeno", tmp_path)]
    segundo = [p.read_bytes() for p in exportar_comparacion(comparacion, "lote_pequeno", tmp_path)]
    assert primero == segundo


def test_exportar_una_comparacion_vacia_escribe_la_cabecera_del_csv(tmp_path):
    ruta_csv, _ = exportar_comparacion(comparar_algoritmos([]), "vacio", tmp_path)
    lineas = ruta_csv.read_text(encoding="utf-8").splitlines()
    assert lineas[0] == ",".join(COLUMNAS_COMPARACION)
    assert len(lineas) == 5  # cabecera + 4 algoritmos con celdas vacías


# ===========================================================================
# Tabla comparativa en consola
# ===========================================================================


def test_la_tabla_comparativa_muestra_una_fila_por_algoritmo():
    texto = tabla_comparativa(comparar_algoritmos(lote_pequeno()), escenario="lote_pequeno.csv")
    lineas = texto.splitlines()
    assert lineas[0] == "== Comparación | escenario=lote_pequeno.csv =="
    assert lineas[1].split() == ["algoritmo", "espera", "retorno", "respuesta", "cpu%", "throughput", "cambios_ctx"]
    filas = {l.split()[0]: l.split() for l in lineas[3:7]}
    assert filas["FCFS"] == ["FCFS", "5.25", "9.50", "5.25", "100.00", "0.24", "3"]
    assert filas["SJF"] == ["SJF", "3.75", "8.00", "3.75", "100.00", "0.24", "3"]
    assert filas["PRIORIDAD"] == ["PRIORIDAD", "4.00", "8.25", "4.00", "100.00", "0.24", "3"]
    assert filas["RR(q=2)"] == ["RR(q=2)", "7.00", "11.25", "1.75", "100.00", "0.24", "8"]


def test_la_tabla_nombra_al_mejor_en_espera_y_en_respuesta():
    lineas = tabla_comparativa(comparar_algoritmos(lote_pequeno())).splitlines()
    assert "Mejor espera media: SJF" in lineas
    assert "Mejor respuesta media: RR(q=2)" in lineas


def test_la_tabla_sin_escenario_ni_procesos_no_falla():
    texto = tabla_comparativa(comparar_algoritmos([]))
    assert texto.splitlines()[0] == "== Comparación =="
    assert "Mejor espera media: -" in texto


# ===========================================================================
# Línea de comandos
# ===========================================================================


def test_main_con_todos_imprime_los_informes_y_la_tabla_comparativa(capsys):
    assert main(["--algoritmo", "todos"]) == 0
    salida = capsys.readouterr().out
    assert "== FCFS | escenario=lote_pequeno.csv ==" in salida
    assert "== Comparación | escenario=lote_pequeno.csv ==" in salida
    assert "Mejor espera media: SJF" in salida
    # La comparación va después de los informes individuales.
    assert salida.index("== RR(q=2) |") < salida.index("== Comparación")


def test_main_con_un_solo_algoritmo_no_imprime_comparacion(capsys):
    assert main(["--algoritmo", "SJF"]) == 0
    assert "Comparación" not in capsys.readouterr().out


@pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="falta matplotlib")
def test_main_exportar_escribe_los_archivos_y_dice_donde(tmp_path, capsys):
    assert main(["--exportar", "--resultados", str(tmp_path)]) == 0
    salida = capsys.readouterr().out
    assert (tmp_path / "procesos_lote_pequeno.csv").is_file()
    assert (tmp_path / "procesos_lote_pequeno.json").is_file()
    assert (tmp_path / "procesos_lote_pequeno.png").is_file()
    assert "[modulo1] exportado:" in salida and "procesos_lote_pequeno.csv" in salida


def test_main_no_exporta_si_no_se_pide(tmp_path, capsys):
    main(["--resultados", str(tmp_path)])
    assert list(tmp_path.iterdir()) == []


def test_main_exportar_exige_comparar_todos_los_algoritmos(tmp_path, capsys):
    assert main(["--algoritmo", "FCFS", "--exportar", "--resultados", str(tmp_path)]) == 2
    assert "todos" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_main_exportar_usa_la_configuracion(tmp_path, capsys):
    main(["--exportar", "--resultados", str(tmp_path), "--quantum", "3"])
    datos = json.loads((tmp_path / "procesos_lote_pequeno.json").read_text(encoding="utf-8"))
    assert datos["algoritmos"][-1]["algoritmo"] == "RR(q=3)"


@pytest.mark.skipif(shutil.which("make") is None, reason="make no está instalado")
def test_make_comparacion_imprime_y_exporta(tmp_path):
    resultado = subprocess.run(
        ["make", "-s", "comparacion", f"RESULTADOS={tmp_path}"],
        cwd=RAIZ, capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert resultado.returncode == 0, resultado.stderr
    assert "== Comparación | escenario=lote_pequeno.csv ==" in resultado.stdout
    assert (tmp_path / "procesos_lote_pequeno.csv").is_file()
    if importlib.util.find_spec("matplotlib") is not None:
        assert (tmp_path / "procesos_lote_pequeno.png").is_file()


def test_main_devuelve_uno_si_no_puede_escribir_la_exportacion(tmp_path, capsys):
    # Una ruta que ya es un archivo no puede ser carpeta de resultados.
    archivo = tmp_path / "no_es_carpeta"
    archivo.write_text("x", encoding="utf-8")
    assert main(["--exportar", "--resultados", str(archivo)]) == 1
    assert "no se pudo exportar" in capsys.readouterr().err
