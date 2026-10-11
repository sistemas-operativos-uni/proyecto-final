"""Registro de algoritmos de planificación y línea de comandos del módulo.

Algoritmos: FCFS, SJF, PRIORIDAD y RR (Round Robin).

Uso desde la raíz del repositorio::

    python -m modulo1_procesos.py.planificador
    python -m modulo1_procesos.py.planificador --algoritmo SJF --escenario escenarios/lote_grande.csv --verbose
    python -m modulo1_procesos.py.planificador --algoritmo RR --quantum 3 --cambio-contexto 1

Códigos de salida: 0 todo bien, 1 escenario inválido, 2 uso incorrecto.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from types import MappingProxyType

from core.cargador_escenarios import ErrorEscenario, cargar_procesos
from core.modelos import Proceso, SimulationConfig

from . import fcfs, prioridad, round_robin, sjf
from .diagrama import informe
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

TODOS = "TODOS"
OK = 0
ESCENARIO_INVALIDO = 1
USO_INCORRECTO = 2
ESCENARIO_POR_DEFECTO = Path(__file__).resolve().parents[2] / "escenarios" / "lote_pequeno.csv"


def _validos() -> str:
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
        raise ValueError(f"algoritmo desconocido {nombre!r}; válidos: {_validos()}") from None
    return algoritmo(procesos, config)


def comparar(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> dict[str, ResultadoPlanificacion]:
    """Corre todos los algoritmos con exactamente el mismo escenario."""
    procesos = tuple(procesos)  # un generador se agotaría tras el primer algoritmo
    return {nombre: algoritmo(procesos, config) for nombre, algoritmo in ALGORITMOS.items()}


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m modulo1_procesos.py.planificador",
        description="Planificación de CPU: FCFS, SJF, Prioridad y Round Robin.",
    )
    parser.add_argument("--escenario", type=Path, default=ESCENARIO_POR_DEFECTO, help="CSV de procesos")
    parser.add_argument("--algoritmo", default="todos", help=f"{_validos()} o todos (por defecto)")
    parser.add_argument("--quantum", type=int, default=2, help="quantum de Round Robin (por defecto 2)")
    parser.add_argument(
        "--cambio-contexto",
        type=int,
        default=0,
        dest="cambio_contexto",
        help="unidades de CPU que cuesta cada cambio de contexto (por defecto 0)",
    )
    parser.add_argument("--verbose", action="store_true", help="imprime el log de cada evento")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        argumentos = _crear_parser().parse_args(argv)
    except SystemExit as salida:  # argparse sale del proceso; se devuelve como código
        return int(salida.code or 0)

    elegido = argumentos.algoritmo.strip().upper()
    if elegido != TODOS and elegido not in ALGORITMOS:
        print(f"algoritmo desconocido {argumentos.algoritmo!r}; válidos: {_validos()}", file=sys.stderr)
        return USO_INCORRECTO

    try:
        # SimulationConfig valida los números: un quantum de 0 o un coste
        # negativo se rechazan aquí, como error de uso y antes de simular.
        config = SimulationConfig(quantum=argumentos.quantum, cambio_contexto=argumentos.cambio_contexto)
    except ValueError as error:
        print(error, file=sys.stderr)
        return USO_INCORRECTO

    try:
        procesos = cargar_procesos(argumentos.escenario)
    except ErrorEscenario as error:
        print(error, file=sys.stderr)
        return ESCENARIO_INVALIDO

    nombres = list(ALGORITMOS) if elegido == TODOS else [elegido]
    for nombre in nombres:
        resultado = planificar(nombre, procesos, config)
        print(informe(resultado, escenario=argumentos.escenario.name, verbose=argumentos.verbose))
        print()
    return OK


if __name__ == "__main__":
    sys.exit(main())
