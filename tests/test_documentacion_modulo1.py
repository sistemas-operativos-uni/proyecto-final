"""Comprueba que IMPLEMENTATIONS.md cita cifras reales del simulador.

El documento discute el efecto convoy, la inanición y el compromiso del
quantum con tablas. Cada fila de esas tablas se recalcula aquí con el
simulador y debe aparecer, letra por letra, en el archivo. Si alguien cambia
un algoritmo y las cifras se desfasan, esta prueba falla y obliga a
actualizar el documento.
"""

from pathlib import Path

import pytest

from core.cargador_escenarios import cargar_procesos
from core.modelos import Proceso, SimulationConfig
from modulo1_procesos.py.metricas_planificacion import metricas_de
from modulo1_procesos.py.planificador import planificar

RAIZ = Path(__file__).resolve().parent.parent
DOCUMENTO = RAIZ / "modulo1_procesos" / "docs" / "IMPLEMENTATIONS.md"
ESCENARIOS = ("lote_pequeno", "lote_grande")
QUANTUMS = (1, 2, 3, 5, 8, 100)
ALGORITMOS = ("FCFS", "SJF", "PRIORIDAD", "RR")


def procesos_de(escenario):
    return cargar_procesos(RAIZ / "escenarios" / f"{escenario}.csv")


def medir(nombre, procesos, **config):
    return metricas_de(planificar(nombre, procesos, SimulationConfig(**config)))


def escenario_inanicion():
    """Escenario sintético: un proceso largo y de baja prioridad entre cortos.

    P000 corre de 0 a 2. PLARGO llega en 1 con ráfaga 20 y prioridad 9.
    Después llega un proceso corto (ráfaga 2, prioridad 1) cada 2 unidades,
    justo cuando termina el anterior, así que siempre hay uno listo.
    """
    procesos = [Proceso("P000", 0, 2, 1, 64, ()), Proceso("PLARGO", 1, 20, 9, 64, ())]
    procesos += [Proceso(f"C{k:02d}", 2 * k, 2, 1, 64, ()) for k in range(1, 16)]
    return procesos


# --- Filas esperadas, una función por tabla del documento --------------------


def filas_comparacion(escenario):
    filas = []
    for nombre in ALGORITMOS:
        m = medir(nombre, procesos_de(escenario))
        filas.append(
            f"| {m.algoritmo} | {m.espera_media:.2f} | {m.retorno_medio:.2f} | {m.respuesta_media:.2f} | {m.cambios_contexto} |"
        )
    return filas


def filas_convoy(escenario):
    procesos = procesos_de(escenario)
    fcfs = {p.pid: p for p in medir("FCFS", procesos).procesos}
    sjf = {p.pid: p for p in medir("SJF", procesos).procesos}
    return [
        f"| {p.id} | {p.rafaga} | {fcfs[p.id].espera} | {sjf[p.id].espera} |"
        for p in sorted(procesos, key=lambda p: (p.llegada, p.id))
        if p.rafaga <= 3
    ]


def filas_espera_de_cortos():
    """Espera media de los procesos con ráfaga de 3 o menos, bajo FCFS y SJF."""
    filas = []
    for escenario in ESCENARIOS:
        procesos = procesos_de(escenario)
        medias = []
        for nombre in ("FCFS", "SJF"):
            cortos = [p.espera for p in medir(nombre, procesos).procesos if p.rafaga <= 3]
            medias.append(sum(cortos) / len(cortos))
        filas.append(f"| {escenario} | {medias[0]:.2f} | {medias[1]:.2f} |")
    return filas


def filas_mayor_espera(escenario):
    procesos = procesos_de(escenario)
    por_pid = {p.id: p for p in procesos}
    filas = []
    for nombre in ("FCFS", "SJF", "PRIORIDAD"):
        peor = max(medir(nombre, procesos).procesos, key=lambda p: (p.espera, -p.llegada))
        origen = por_pid[peor.pid]
        filas.append(f"| {nombre} | {peor.pid} | {origen.rafaga} | {origen.prioridad} | {peor.espera} |")
    return filas


def filas_inanicion():
    procesos = escenario_inanicion()
    filas = []
    for nombre in ("FCFS", "SJF", "PRIORIDAD"):
        m = medir(nombre, procesos)
        largo = next(p for p in m.procesos if p.pid == "PLARGO")
        cortos = [p.espera for p in m.procesos if p.pid.startswith("C")]
        filas.append(f"| {nombre} | {largo.espera} | {sum(cortos) / len(cortos):.2f} |")
    return filas


def filas_quantum(escenario):
    procesos = procesos_de(escenario)
    filas = []
    for q in QUANTUMS:
        sin_coste = medir("RR", procesos, quantum=q)
        con_coste = medir("RR", procesos, quantum=q, cambio_contexto=1)
        filas.append(
            f"| {q} | {sin_coste.espera_media:.2f} | {sin_coste.respuesta_media:.2f} | "
            f"{sin_coste.cambios_contexto} | {con_coste.utilizacion_cpu:.1f} |"
        )
    return filas


# --- Pruebas -----------------------------------------------------------------


@pytest.fixture(scope="module")
def texto():
    assert DOCUMENTO.is_file(), f"falta {DOCUMENTO.relative_to(RAIZ)}"
    return DOCUMENTO.read_text(encoding="utf-8")


def test_el_documento_trata_los_tres_temas(texto):
    minusculas = texto.lower()
    for tema in ("efecto convoy", "inanición", "quantum"):
        assert tema in minusculas, tema


def test_el_documento_dice_que_el_escenario_de_inanicion_es_sintetico(texto):
    assert "sintético" in texto.lower()


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_la_comparacion_de_algoritmos_cita_cifras_reales(texto, escenario):
    for fila in filas_comparacion(escenario):
        assert fila in texto, fila


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_la_tabla_del_efecto_convoy_cita_cifras_reales(texto, escenario):
    filas = filas_convoy(escenario)
    assert filas  # cada escenario tiene procesos cortos que mostrar
    for fila in filas:
        assert fila in texto, fila


def test_la_espera_media_de_los_procesos_cortos_cita_cifras_reales(texto):
    for fila in filas_espera_de_cortos():
        assert fila in texto, fila


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_la_tabla_de_mayor_espera_cita_cifras_reales(texto, escenario):
    for fila in filas_mayor_espera(escenario):
        assert fila in texto, fila


def test_la_tabla_de_inanicion_cita_cifras_reales(texto):
    for fila in filas_inanicion():
        assert fila in texto, fila


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_la_tabla_del_quantum_cita_cifras_reales(texto, escenario):
    for fila in filas_quantum(escenario):
        assert fila in texto, fila


def test_el_escenario_de_inanicion_muestra_inanicion_de_verdad():
    # Si esta prueba falla, la tabla del documento ya no demuestra lo que dice.
    procesos = escenario_inanicion()
    largo = {n: next(p for p in medir(n, procesos).procesos if p.pid == "PLARGO") for n in ("FCFS", "SJF", "PRIORIDAD")}
    assert largo["FCFS"].espera == 1
    assert largo["SJF"].espera > 20 and largo["PRIORIDAD"].espera > 20
    assert largo["SJF"].fin == 52  # espera al último de los cortos (que termina en 32) y luego corre sus 20
