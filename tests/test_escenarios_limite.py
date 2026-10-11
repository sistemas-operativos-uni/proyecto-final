"""Escenarios límite de la planificación (Fase 8 del Módulo 1).

Cada escenario corre con los cuatro algoritmos. Los resultados exactos se
calculan a mano en cada prueba. Para los escenarios grandes, donde el
resultado exacto no se escribe a mano, se comprueban invariantes que deben
cumplirse en cualquier corrida:

  - cada proceso recibe de CPU exactamente su ráfaga,
  - la línea de tiempo es continua desde 0 y sin solapes,
  - retorno = espera + ráfaga, y el tiempo total se reparte entre CPU, ocio y
    cambios de contexto,
  - las métricas derivadas de los eventos coinciden con el resultado,
  - la corrida es determinista y no depende del orden de la lista de entrada.
"""

import random
import time
from collections import Counter

import pytest

from core.modelos import Proceso, SimulationConfig
from modulo1_procesos.py.metricas_planificacion import metricas_de
from modulo1_procesos.py.motor import Segmento
from modulo1_procesos.py.planificador import planificar

ALGORITMOS = ["FCFS", "SJF", "PRIORIDAD", "RR"]
LIMITE_SEGUNDOS = 5  # holgado a propósito: la prueba detecta explosiones, no mide velocidad


def P(id, llegada, rafaga, prio=1):
    return Proceso(id, llegada, rafaga, prio, 64, ())


def correr(nombre, procesos, **config):
    return planificar(nombre, procesos, SimulationConfig(**config))


def orden(resultado):
    return [s.pid for s in resultado.segmentos if s.pid is not None]


def verificar_invariantes(resultado, procesos):
    """Las propiedades que toda corrida correcta cumple, sea cual sea el escenario."""
    esperadas = {p.id: p.rafaga for p in procesos}

    recibido = Counter()
    for s in resultado.segmentos:
        if s.pid is not None:
            recibido[s.pid] += s.fin - s.inicio
    assert recibido == esperadas

    assert resultado.segmentos[0].inicio == 0
    for anterior, siguiente in zip(resultado.segmentos, resultado.segmentos[1:]):
        assert anterior.fin == siguiente.inicio

    metricas = metricas_de(resultado)
    assert len(resultado.procesos) == len(procesos)
    for visto, derivado in zip(resultado.procesos, metricas.procesos):
        assert visto.retorno == visto.espera + visto.rafaga
        assert visto.inicio >= visto.llegada and visto.fin >= visto.inicio + visto.rafaga
        # Segunda derivación, desde los eventos: debe coincidir con la del motor.
        assert (derivado.pid, derivado.espera, derivado.retorno, derivado.respuesta) == (
            visto.pid, visto.espera, visto.retorno, visto.respuesta
        )  # fmt: skip
    assert metricas.tiempo_total == metricas.tiempo_cpu + metricas.tiempo_ocioso + metricas.tiempo_cambios
    assert metricas.tiempo_cpu == sum(esperadas.values())
    assert metricas.cambios_contexto == resultado.cambios_contexto


def generar(semilla, cantidad, llegada_max=60, rafaga_max=12, prioridades=5):
    """Escenario pseudoaleatorio pero reproducible: la misma semilla da el mismo lote."""
    azar = random.Random(semilla)
    return [
        P(f"P{i:03d}", azar.randint(0, llegada_max), azar.randint(1, rafaga_max), azar.randint(1, prioridades))
        for i in range(1, cantidad + 1)
    ]


# ===========================================================================
# 1 proceso
# ===========================================================================


@pytest.mark.parametrize("nombre", ["FCFS", "SJF", "PRIORIDAD"])
def test_un_proceso_sin_expropiacion(nombre):
    r = correr(nombre, [P("P001", 0, 5)])
    assert r.segmentos == (Segmento("P001", 0, 5),)
    (p,) = r.procesos
    assert (p.espera, p.retorno, p.respuesta, p.fin) == (0, 5, 0, 5)
    assert r.cambios_contexto == 0


def test_un_proceso_en_round_robin_se_parte_en_turnos_sin_cambios_de_contexto():
    r = correr("RR", [P("P001", 0, 5)], quantum=2)
    assert r.segmentos == (Segmento("P001", 0, 2), Segmento("P001", 2, 4), Segmento("P001", 4, 5))
    assert r.cambios_contexto == 0


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_un_proceso_de_una_sola_unidad(nombre):
    r = correr(nombre, [P("P001", 0, 1)])
    assert r.segmentos == (Segmento("P001", 0, 1),)
    assert metricas_de(r).utilizacion_cpu == 100.0


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_un_proceso_nunca_paga_cambio_de_contexto(nombre):
    # quantum 100 para que Round Robin no parta la ráfaga y el resultado sea comparable.
    r = correr(nombre, [P("P001", 3, 4)], cambio_contexto=5, quantum=100)
    assert r.segmentos == (Segmento(None, 0, 3), Segmento("P001", 3, 7))  # solo ocio inicial
    assert r.cambios_contexto == 0
    verificar_invariantes(r, [P("P001", 3, 4)])


# ===========================================================================
# 100 procesos generados
# ===========================================================================


@pytest.mark.parametrize("semilla", [0, 1, 2])
@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_cumplen_los_invariantes(nombre, semilla):
    procesos = generar(semilla, 100)
    verificar_invariantes(correr(nombre, procesos), procesos)


@pytest.mark.parametrize("coste", [1, 3])
@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_con_coste_de_cambio_de_contexto(nombre, coste):
    procesos = generar(7, 100)
    r = correr(nombre, procesos, cambio_contexto=coste)
    verificar_invariantes(r, procesos)
    assert metricas_de(r).tiempo_cambios == coste * r.cambios_contexto


@pytest.mark.parametrize("quantum", [1, 3, 20])
def test_cien_procesos_en_round_robin_con_distintos_quantums(quantum):
    procesos = generar(3, 100)
    r = correr("RR", procesos, quantum=quantum)
    verificar_invariantes(r, procesos)
    assert all(s.fin - s.inicio <= quantum for s in r.segmentos if s.pid)


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_dan_el_mismo_resultado_sin_importar_el_orden_de_entrada(nombre):
    procesos = generar(5, 100)
    barajados = list(procesos)
    random.Random(99).shuffle(barajados)
    assert correr(nombre, procesos).segmentos == correr(nombre, barajados).segmentos


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_son_deterministas(nombre):
    procesos = generar(11, 100)
    assert correr(nombre, procesos) == correr(nombre, procesos)


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_dejan_tres_transiciones_por_proceso_sin_expropiacion(nombre):
    procesos = generar(2, 100)
    r = correr(nombre, procesos)
    transiciones = [e for e in r.eventos if e.accion == "TRANSICION"]
    if nombre == "RR":
        assert len(transiciones) >= 300  # cada expropiación agrega dos más
    else:
        assert len(transiciones) == 300


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_corren_en_tiempo_razonable(nombre):
    procesos = generar(4, 100, rafaga_max=20)
    inicio = time.perf_counter()
    correr(nombre, procesos, quantum=1)  # quantum 1 es el peor caso de Round Robin
    assert time.perf_counter() - inicio < LIMITE_SEGUNDOS


# ===========================================================================
# Ráfagas muy desiguales
# ===========================================================================

LARGA = 5000


def test_un_proceso_enorme_con_uno_diminuto_en_fcfs_es_el_peor_convoy():
    r = correr("FCFS", [P("P001", 0, LARGA), P("P002", 1, 1)])
    esperas = {p.pid: p.espera for p in r.procesos}
    assert esperas == {"P001": 0, "P002": LARGA - 1}  # el diminuto espera casi todo el tiempo del enorme


def test_sjf_y_prioridad_sin_expropiacion_tampoco_interrumpen_al_enorme():
    # En t=0 solo P001 está listo: arranca y nadie lo interrumpe.
    for nombre in ("SJF", "PRIORIDAD"):
        r = correr(nombre, [P("P001", 0, LARGA), P("P002", 1, 1)])
        assert orden(r) == ["P001", "P002"]
        assert {p.pid: p.espera for p in r.procesos}["P002"] == LARGA - 1


def test_round_robin_libera_al_diminuto_en_el_primer_turno():
    r = correr("RR", [P("P001", 0, LARGA), P("P002", 1, 1)], quantum=1)
    por_pid = {p.pid: p for p in r.procesos}
    # P002 llega en t=1, cuando P001 agota su primer quantum, y entra antes.
    assert (por_pid["P002"].inicio, por_pid["P002"].espera, por_pid["P002"].respuesta) == (1, 0, 0)
    assert por_pid["P001"].fin == LARGA + 1 and por_pid["P001"].espera == 1
    assert len(r.segmentos) == LARGA + 1  # un segmento por unidad de la ráfaga enorme y uno del diminuto


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_rafagas_de_1_a_5000_mezcladas_cumplen_los_invariantes(nombre):
    procesos = [P("P001", 0, 5000), P("P002", 0, 1), P("P003", 2, 4000, 2), P("P004", 3, 1, 3), P("P005", 10, 250, 1)]
    verificar_invariantes(correr(nombre, procesos, quantum=7), procesos)


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_veinte_procesos_diminutos_y_uno_enorme_cumplen_los_invariantes(nombre):
    procesos = [P("P000", 0, 3000)] + [P(f"P{i:03d}", i, 1) for i in range(1, 21)]
    verificar_invariantes(correr(nombre, procesos, quantum=2), procesos)


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_una_llegada_lejanisima_salta_el_ocio_sin_avanzar_unidad_por_unidad(nombre):
    inicio = time.perf_counter()
    r = correr(nombre, [P("P001", 0, 2), P("P002", 10_000_000, 3)], quantum=100)
    assert time.perf_counter() - inicio < 1
    assert r.segmentos == (Segmento("P001", 0, 2), Segmento(None, 2, 10_000_000), Segmento("P002", 10_000_000, 10_000_003))
    assert metricas_de(r).tiempo_ocioso == 10_000_000 - 2


# ===========================================================================
# Llegadas idénticas
# ===========================================================================

# Cinco procesos que llegan juntos en t=0, con ráfagas y prioridades distintas.
RAFAGAS = [4, 1, 3, 1, 2]
PRIORIDADES = [3, 1, 2, 1, 2]
JUNTOS = [P(f"P00{i}", 0, r, pr) for i, (r, pr) in enumerate(zip(RAFAGAS, PRIORIDADES), start=1)]


@pytest.mark.parametrize(
    "nombre, esperado",
    [
        ("FCFS", ["P001", "P002", "P003", "P004", "P005"]),  # empate de llegada: gana el id
        ("SJF", ["P002", "P004", "P005", "P003", "P001"]),  # ráfaga 1, 1, 2, 3, 4; empates por id
        ("PRIORIDAD", ["P002", "P004", "P003", "P005", "P001"]),  # prioridad 1, 1, 2, 2, 3; empates por id
        ("RR", ["P001", "P002", "P003", "P004", "P005", "P001", "P003"]),  # quantum 2, cola por id
    ],
)
def test_llegadas_identicas_siguen_el_criterio_de_cada_algoritmo(nombre, esperado):
    r = correr(nombre, JUNTOS, quantum=2)
    assert orden(r) == esperado
    verificar_invariantes(r, JUNTOS)


def test_round_robin_con_llegadas_identicas_da_los_tiempos_exactos():
    r = correr("RR", JUNTOS, quantum=2)
    assert r.segmentos == (
        Segmento("P001", 0, 2), Segmento("P002", 2, 3), Segmento("P003", 3, 5), Segmento("P004", 5, 6),
        Segmento("P005", 6, 8), Segmento("P001", 8, 10), Segmento("P003", 10, 11),
    )  # fmt: skip
    assert {p.pid: p.fin for p in r.procesos} == {"P001": 10, "P002": 3, "P003": 11, "P004": 6, "P005": 8}


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_identicos_salen_en_orden_de_id(nombre):
    procesos = [P(f"P{i:03d}", 0, 3, 2) for i in range(100, 0, -1)]  # entran al revés
    r = correr(nombre, procesos, quantum=3)
    assert orden(r) == [f"P{i:03d}" for i in range(1, 101)]
    verificar_invariantes(r, procesos)


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_cien_procesos_que_llegan_juntos_con_ráfagas_distintas(nombre):
    procesos = [P(f"P{i:03d}", 0, 1 + (i * 7) % 13, 1 + i % 4) for i in range(1, 101)]
    verificar_invariantes(correr(nombre, procesos), procesos)


@pytest.mark.parametrize("nombre", ALGORITMOS)
def test_llegadas_identicas_despues_de_un_ocio_inicial(nombre):
    procesos = [P("P001", 5, 2), P("P002", 5, 2), P("P003", 5, 2)]
    r = correr(nombre, procesos, quantum=2)
    assert r.segmentos[0] == Segmento(None, 0, 5)
    assert orden(r) == ["P001", "P002", "P003"]
    verificar_invariantes(r, procesos)
