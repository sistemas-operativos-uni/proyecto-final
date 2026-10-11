"""Pruebas del PCB, sus estados y la tabla de procesos (Fase 1 del Módulo 1)."""

import pytest

from core.cargador_escenarios import cargar_procesos
from core.modelos import Evento, Proceso
from modulo1_procesos.py.pcb import (
    PCB,
    TRANSICIONES,
    EstadoProceso,
    TablaProcesos,
    TransicionInvalida,
)

NUEVO = EstadoProceso.NUEVO
LISTO = EstadoProceso.LISTO
EJECUCION = EstadoProceso.EJECUCION
BLOQUEADO = EstadoProceso.BLOQUEADO
TERMINADO = EstadoProceso.TERMINADO


def proceso(id="P001", llegada=0, rafaga=5, prioridad=2):
    return Proceso(id, llegada, rafaga, prioridad, 128, ("SO101",))


def pcb_en(estado, **kwargs):
    """Lleva un PCB nuevo hasta `estado` por el camino válido más corto."""
    pcb = PCB.desde_proceso(proceso(**kwargs))
    camino = {
        NUEVO: [],
        LISTO: [LISTO],
        EJECUCION: [LISTO, EJECUCION],
        BLOQUEADO: [LISTO, EJECUCION, BLOQUEADO],
        TERMINADO: [LISTO, EJECUCION, TERMINADO],
    }[estado]
    for paso in camino:
        if paso is TERMINADO:
            pcb.ejecutar(pcb.rafaga_restante)
        pcb.transicionar(paso, pcb.ultimo_cambio)
    return pcb


# --- Estados ---------------------------------------------------------------


def test_los_cinco_estados_del_ciclo_de_vida_existen():
    assert [e.name for e in EstadoProceso] == [
        "NUEVO",
        "LISTO",
        "EJECUCION",
        "BLOQUEADO",
        "TERMINADO",
    ]


def test_tabla_de_transiciones_permitidas():
    assert TRANSICIONES == {
        NUEVO: {LISTO},
        LISTO: {EJECUCION},
        EJECUCION: {LISTO, BLOQUEADO, TERMINADO},
        BLOQUEADO: {LISTO},
        TERMINADO: set(),
    }


# --- PCB: creación ---------------------------------------------------------


def test_pcb_nace_nuevo_con_los_datos_del_proceso():
    pcb = PCB.desde_proceso(proceso("P002", llegada=1, rafaga=3, prioridad=1))
    assert pcb.pid == "P002"
    assert pcb.estado is NUEVO
    assert (pcb.llegada, pcb.prioridad) == (1, 1)
    assert (pcb.rafaga_total, pcb.rafaga_restante) == (3, 3)
    assert pcb.t_primera_cpu is None and pcb.t_fin is None
    assert pcb.ultimo_cambio == 1


@pytest.mark.parametrize("campo", ["pid", "estado", "rafaga_restante", "t_fin"])
def test_pcb_no_permite_asignar_campos_de_estado_desde_fuera(campo):
    pcb = PCB.desde_proceso(proceso())
    with pytest.raises(AttributeError):
        setattr(pcb, campo, 0)


# --- PCB: transiciones válidas ---------------------------------------------


@pytest.mark.parametrize(
    "origen, destino",
    [
        (NUEVO, LISTO),
        (LISTO, EJECUCION),
        (EJECUCION, LISTO),
        (EJECUCION, BLOQUEADO),
        (BLOQUEADO, LISTO),
    ],
)
def test_transicion_valida_cambia_el_estado(origen, destino):
    pcb = pcb_en(origen, rafaga=5)
    if origen is EJECUCION:
        pcb.ejecutar(2)  # queda ráfaga pendiente: puede expropiarse o bloquearse
    pcb.transicionar(destino, pcb.ultimo_cambio + 1)
    assert pcb.estado is destino


def test_ejecucion_a_terminado_exige_haber_consumido_la_rafaga():
    pcb = pcb_en(EJECUCION, rafaga=3)
    pcb.ejecutar(3)
    pcb.transicionar(TERMINADO, 3)
    assert pcb.estado is TERMINADO and pcb.t_fin == 3


def test_primera_cpu_se_fija_solo_la_primera_vez():
    pcb = PCB.desde_proceso(proceso(llegada=0, rafaga=4))
    pcb.transicionar(LISTO, 0)
    pcb.transicionar(EJECUCION, 3)
    pcb.ejecutar(2)
    pcb.transicionar(LISTO, 5)  # expropiado por Round Robin
    pcb.transicionar(EJECUCION, 9)  # vuelve a la CPU
    assert pcb.t_primera_cpu == 3


# --- PCB: transiciones inválidas -------------------------------------------


@pytest.mark.parametrize(
    "origen, destino",
    [
        (NUEVO, EJECUCION),
        (NUEVO, BLOQUEADO),
        (NUEVO, TERMINADO),
        (LISTO, BLOQUEADO),
        (LISTO, TERMINADO),
        (LISTO, NUEVO),
        (BLOQUEADO, EJECUCION),
        (BLOQUEADO, TERMINADO),
        (TERMINADO, LISTO),
        (TERMINADO, EJECUCION),
        (TERMINADO, NUEVO),
    ],
)
def test_transicion_invalida_lanza_y_no_cambia_el_estado(origen, destino):
    pcb = pcb_en(origen)
    antes = (pcb.estado, pcb.ultimo_cambio, pcb.rafaga_restante)
    with pytest.raises(TransicionInvalida):
        pcb.transicionar(destino, pcb.ultimo_cambio + 1)
    assert (pcb.estado, pcb.ultimo_cambio, pcb.rafaga_restante) == antes


def test_transicion_invalida_es_un_value_error():
    assert issubclass(TransicionInvalida, ValueError)


def test_el_mensaje_nombra_el_proceso_y_los_dos_estados():
    pcb = PCB.desde_proceso(proceso("P009"))
    with pytest.raises(TransicionInvalida, match=r"P009.*NUEVO.*EJECUCION"):
        pcb.transicionar(EJECUCION, 0)


# --- PCB: invariantes de ráfaga restante -----------------------------------


def test_ejecutar_descuenta_de_la_rafaga_restante():
    pcb = pcb_en(EJECUCION, rafaga=5)
    pcb.ejecutar(2)
    assert pcb.rafaga_restante == 3 and pcb.rafaga_total == 5


def test_ejecutar_fuera_de_ejecucion_lanza():
    pcb = pcb_en(LISTO)
    with pytest.raises(TransicionInvalida):
        pcb.ejecutar(1)
    assert pcb.rafaga_restante == 5


@pytest.mark.parametrize("unidades", [0, -1, 1.5, True, "2"])
def test_ejecutar_rechaza_unidades_invalidas(unidades):
    pcb = pcb_en(EJECUCION)
    with pytest.raises(ValueError):
        pcb.ejecutar(unidades)
    assert pcb.rafaga_restante == 5


def test_ejecutar_mas_que_la_rafaga_restante_lanza_y_no_baja_de_cero():
    pcb = pcb_en(EJECUCION, rafaga=3)
    with pytest.raises(ValueError):
        pcb.ejecutar(4)
    assert pcb.rafaga_restante == 3


def test_terminar_con_rafaga_pendiente_lanza():
    pcb = pcb_en(EJECUCION, rafaga=5)
    pcb.ejecutar(4)
    with pytest.raises(TransicionInvalida, match="ráfaga"):
        pcb.transicionar(TERMINADO, 4)
    assert pcb.estado is EJECUCION


@pytest.mark.parametrize("destino", [LISTO, BLOQUEADO])
def test_con_rafaga_agotada_solo_se_puede_terminar(destino):
    pcb = pcb_en(EJECUCION, rafaga=2)
    pcb.ejecutar(2)
    with pytest.raises(TransicionInvalida):
        pcb.transicionar(destino, 2)
    assert pcb.estado is EJECUCION


# --- PCB: tiempo -----------------------------------------------------------


def test_el_instante_no_puede_retroceder():
    pcb = PCB.desde_proceso(proceso(llegada=0))
    pcb.transicionar(LISTO, 4)
    with pytest.raises(ValueError, match="retroced"):
        pcb.transicionar(EJECUCION, 3)
    assert pcb.estado is LISTO and pcb.ultimo_cambio == 4


def test_no_puede_entrar_a_listo_antes_de_su_llegada():
    pcb = PCB.desde_proceso(proceso(llegada=5))
    with pytest.raises(ValueError):
        pcb.transicionar(LISTO, 4)
    assert pcb.estado is NUEVO


@pytest.mark.parametrize("instante", [-1, 1.5, True, None])
def test_instante_invalido_lanza(instante):
    pcb = PCB.desde_proceso(proceso())
    with pytest.raises(ValueError):
        pcb.transicionar(LISTO, instante)


# --- TablaProcesos ---------------------------------------------------------


def test_tabla_registra_procesos_nuevos_en_orden():
    tabla = TablaProcesos()
    tabla.registrar(proceso("P001"))
    tabla.registrar(proceso("P002"))
    assert len(tabla) == 2
    assert [p.pid for p in tabla] == ["P001", "P002"]
    assert tabla["P002"].estado is NUEVO


def test_tabla_rechaza_pid_duplicado():
    tabla = TablaProcesos()
    tabla.registrar(proceso("P001"))
    with pytest.raises(ValueError, match="P001"):
        tabla.registrar(proceso("P001"))


def test_tabla_lanza_key_error_con_pid_desconocido():
    with pytest.raises(KeyError):
        TablaProcesos().transicionar("P404", LISTO, 0)


def test_tabla_devuelve_un_evento_por_transicion():
    tabla = TablaProcesos()
    tabla.registrar(proceso("P001"))
    evento = tabla.transicionar("P001", LISTO, 0)
    assert isinstance(evento, Evento)
    assert (evento.instante, evento.modulo, evento.entidad) == (0, "procesos", "P001")
    assert evento.accion == "TRANSICION"
    assert evento.datos["desde"] == "NUEVO" and evento.datos["hacia"] == "LISTO"
    assert tabla.eventos == (evento,)


def test_una_transicion_invalida_no_deja_evento():
    tabla = TablaProcesos()
    tabla.registrar(proceso("P001"))
    with pytest.raises(TransicionInvalida):
        tabla.transicionar("P001", EJECUCION, 0)
    assert tabla.eventos == ()


def test_solo_un_proceso_puede_estar_en_ejecucion():
    tabla = TablaProcesos()
    for pid in ("P001", "P002"):
        tabla.registrar(proceso(pid))
        tabla.transicionar(pid, LISTO, 0)
    tabla.transicionar("P001", EJECUCION, 0)
    assert tabla.en_ejecucion is tabla["P001"]
    with pytest.raises(TransicionInvalida, match="P001"):
        tabla.transicionar("P002", EJECUCION, 0)
    assert tabla["P002"].estado is LISTO
    assert len(tabla.eventos) == 3  # 2 admisiones + 1 despacho


def test_en_ejecucion_es_none_cuando_la_cpu_esta_libre():
    assert TablaProcesos().en_ejecucion is None


def test_la_tabla_rechaza_instantes_que_retroceden_entre_procesos():
    tabla = TablaProcesos()
    tabla.registrar(proceso("P001"))
    tabla.registrar(proceso("P002"))
    tabla.transicionar("P001", LISTO, 5)
    with pytest.raises(ValueError, match="retroced"):
        tabla.transicionar("P002", LISTO, 2)
    assert tabla["P002"].estado is NUEVO


# --- Aceptación: lote_pequeno.csv bajo FCFS --------------------------------


def test_ciclo_de_vida_de_lote_pequeno_coincide_con_el_oraculo_fcfs():
    tabla = TablaProcesos()
    for p in cargar_procesos("escenarios/lote_pequeno.csv"):
        tabla.registrar(p)

    # (instante, pid, estado destino); la CPU ejecuta ráfagas completas.
    guion = [
        (0, "P001", LISTO), (0, "P001", EJECUCION),
        (1, "P002", LISTO),
        (2, "P003", LISTO),
        (4, "P004", LISTO),
        (5, "P001", TERMINADO), (5, "P002", EJECUCION),
        (8, "P002", TERMINADO), (8, "P003", EJECUCION),
        (15, "P003", TERMINADO), (15, "P004", EJECUCION),
        (17, "P004", TERMINADO),
    ]  # fmt: skip
    for instante, pid, destino in guion:
        if destino is TERMINADO:
            tabla[pid].ejecutar(tabla[pid].rafaga_restante)
        tabla.transicionar(pid, destino, instante)

    assert all(p.estado is TERMINADO for p in tabla)
    assert [tabla[p].t_fin for p in ("P001", "P002", "P003", "P004")] == [5, 8, 15, 17]
    esperas = [tabla[p].t_primera_cpu - tabla[p].llegada for p in ("P001", "P002", "P003", "P004")]
    assert esperas == [0, 4, 6, 11]
    assert len(tabla.eventos) == len(guion)  # un evento por transición del guion
