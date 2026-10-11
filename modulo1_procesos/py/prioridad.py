"""Planificación por prioridad, sin expropiación.

Convención del proyecto: un número de prioridad menor significa más
prioridad. P002 con prioridad 1 pasa antes que P003 con prioridad 3.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.modelos import Proceso, SimulationConfig

from .motor import ResultadoPlanificacion, planificar_no_expropiativo
from .pcb import PCB

NOMBRE = "PRIORIDAD"


def criterio(pcb: PCB) -> tuple:
    # Primero la prioridad; con prioridades iguales, llegada y luego id.
    # Sin expropiación: un proceso más prioritario que llega mientras otro
    # corre espera a que ese termine. Una prioridad baja puede sufrir
    # inanición; el envejecimiento (aging) queda como mejora de la Fase 8.
    return (pcb.prioridad, pcb.llegada, pcb.pid)


def planificar(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> ResultadoPlanificacion:
    return planificar_no_expropiativo(NOMBRE, procesos, config, criterio)
