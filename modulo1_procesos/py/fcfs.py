"""FCFS (first come, first served): el primero en llegar es el primero en correr."""

from __future__ import annotations

from collections.abc import Iterable

from core.modelos import Proceso, SimulationConfig

from .motor import ResultadoPlanificacion, planificar_no_expropiativo
from .pcb import PCB

NOMBRE = "FCFS"


def criterio(pcb: PCB) -> tuple:
    # Solo cuenta la llegada. Ni la ráfaga ni la prioridad influyen, y por eso
    # un proceso largo al frente retrasa a todos (efecto convoy). El id
    # desempata llegadas iguales.
    return (pcb.llegada, pcb.pid)


def planificar(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> ResultadoPlanificacion:
    return planificar_no_expropiativo(NOMBRE, procesos, config, criterio)
