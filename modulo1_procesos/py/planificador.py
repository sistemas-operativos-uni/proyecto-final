"""Registro de algoritmos de planificación.

Algoritmos: FCFS, SJF, PRIORIDAD y RR (Round Robin).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from types import MappingProxyType

from core.modelos import Proceso, SimulationConfig

from . import fcfs, prioridad, round_robin, sjf
from .motor import ResultadoPlanificacion

Algoritmo = Callable[[Iterable[Proceso], SimulationConfig | None], ResultadoPlanificacion]

# Registro de solo lectura. Es el patrón Strategy: el resto del código elige un
# algoritmo por nombre y no conoce sus clases. Añadir uno nuevo es una entrada
# más aquí, sin tocar a quien lo invoca.
ALGORITMOS: MappingProxyType[str, Algoritmo] = MappingProxyType(
    {
        fcfs.NOMBRE: fcfs.planificar,
        sjf.NOMBRE: sjf.planificar,
        prioridad.NOMBRE: prioridad.planificar,
        round_robin.NOMBRE: round_robin.planificar,
    }
)


def validos() -> str:
    return ", ".join(ALGORITMOS)


def planificar(
    nombre: str, procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> ResultadoPlanificacion:
    """Ejecuta el algoritmo `nombre`, sin distinguir mayúsculas ni espacios."""
    clave = nombre.strip().upper()
    try:
        algoritmo = ALGORITMOS[clave]
    except KeyError:
        # Un nombre mal escrito falla aquí y nombra las opciones; no cae a un
        # algoritmo por defecto que ocultaría el error.
        raise ValueError(f"algoritmo desconocido {nombre!r}; válidos: {validos()}") from None
    return algoritmo(procesos, config)


def comparar(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> dict[str, ResultadoPlanificacion]:
    """Corre todos los algoritmos con exactamente el mismo escenario."""
    procesos = tuple(procesos)  # un generador se agotaría tras el primer algoritmo
    return {nombre: algoritmo(procesos, config) for nombre, algoritmo in ALGORITMOS.items()}
