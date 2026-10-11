"""SJF no expropiativo (shortest job first): corre el proceso de menor ráfaga."""

from __future__ import annotations

from collections.abc import Iterable

from core.modelos import Proceso, SimulationConfig

from .motor import ResultadoPlanificacion, planificar_no_expropiativo
from .pcb import PCB

NOMBRE = "SJF"


def criterio(pcb: PCB) -> tuple:
    # Menor ráfaga primero. Con ráfagas iguales gana quien llegó antes y, si
    # también empatan, el id menor. Sin esa cadena de desempate el resultado
    # dependería del orden en que venga la lista.
    # Riesgo conocido: un proceso largo puede esperar indefinidamente si
    # siguen llegando procesos cortos (inanición).
    return (pcb.rafaga_total, pcb.llegada, pcb.pid)


def planificar(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> ResultadoPlanificacion:
    return planificar_no_expropiativo(NOMBRE, procesos, config, criterio)
