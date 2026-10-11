"""Línea de comandos del Módulo 1: planificación de CPU.

Uso desde la raíz del repositorio::

    python -m modulo1_procesos.py.cli
    python -m modulo1_procesos.py.cli --algoritmo SJF --escenario escenarios/lote_grande.csv --verbose
    python -m modulo1_procesos.py.cli --algoritmo RR --quantum 3 --cambio-contexto 1
    python -m modulo1_procesos.py.cli --exportar --resultados resultados

Con `--algoritmo todos` (el valor por defecto) imprime además la tabla
comparativa. `--exportar` guarda esa comparación en CSV, JSON y un gráfico PNG.

Códigos de salida: 0 todo bien, 1 escenario inválido o error al exportar, 2 uso incorrecto.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from core.cargador_escenarios import ErrorEscenario, cargar_procesos
from core.modelos import SimulationConfig

from .adaptador import ESCENARIO_POR_DEFECTO
from .diagrama import informe, tabla_comparativa
from .graficos import graficar_comparacion
from .metricas_planificacion import ComparacionAlgoritmos, exportar_comparacion
from .planificador import ALGORITMOS, comparar, planificar, validos

TODOS = "TODOS"
OK = 0
ESCENARIO_INVALIDO = 1
USO_INCORRECTO = 2
RESULTADOS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "resultados"

def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m modulo1_procesos.py.cli",
        description="Planificación de CPU: FCFS, SJF, Prioridad y Round Robin.",
    )
    parser.add_argument("--escenario", type=Path, default=ESCENARIO_POR_DEFECTO, help="CSV de procesos")
    parser.add_argument("--algoritmo", default="todos", help=f"{validos()} o todos (por defecto)")
    parser.add_argument("--quantum", type=int, default=2, help="quantum de Round Robin (por defecto 2)")
    parser.add_argument(
        "--cambio-contexto",
        type=int,
        default=0,
        dest="cambio_contexto",
        help="unidades de CPU que cuesta cada cambio de contexto (por defecto 0)",
    )
    parser.add_argument("--verbose", action="store_true", help="imprime el log de cada evento")
    parser.add_argument(
        "--exportar", action="store_true", help="guarda la comparación en procesos_<escenario>.csv y .json"
    )
    parser.add_argument(
        "--resultados", type=Path, default=RESULTADOS_POR_DEFECTO, help="carpeta de exportación (por defecto resultados/)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        argumentos = _crear_parser().parse_args(argv)
    except SystemExit as salida:  # argparse sale del proceso; se devuelve como código
        return int(salida.code or 0)

    elegido = argumentos.algoritmo.strip().upper()
    if elegido != TODOS and elegido not in ALGORITMOS:
        print(f"algoritmo desconocido {argumentos.algoritmo!r}; válidos: {validos()}", file=sys.stderr)
        return USO_INCORRECTO

    if argumentos.exportar and elegido != TODOS:
        # La exportación guarda una comparación; con un solo algoritmo no hay
        # nada que comparar y el archivo saldría engañoso.
        print("--exportar compara algoritmos: use --algoritmo todos", file=sys.stderr)
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

    if elegido != TODOS:
        print(informe(planificar(elegido, procesos, config), escenario=argumentos.escenario.name, verbose=argumentos.verbose))
        print()
        return OK

    # Los algoritmos corren una sola vez: los informes y la comparación leen
    # los mismos resultados, y por eso sus cifras coinciden.
    resultados = comparar(procesos, config)
    for resultado in resultados.values():
        print(informe(resultado, escenario=argumentos.escenario.name, verbose=argumentos.verbose))
        print()
    comparacion = ComparacionAlgoritmos.desde_resultados(resultados.values())
    print(tabla_comparativa(comparacion, escenario=argumentos.escenario.name))
    print()

    if argumentos.exportar:
        try:
            ruta_csv, ruta_json = exportar_comparacion(comparacion, argumentos.escenario, argumentos.resultados)
        except OSError as error:
            print(f"no se pudo exportar: {error}", file=sys.stderr)
            return ESCENARIO_INVALIDO
        print(f"[modulo1] exportado: {ruta_csv} y {ruta_json}")
        try:
            print(f"[modulo1] gráfico: {graficar_comparacion(comparacion, argumentos.escenario, argumentos.resultados)}")
        except (OSError, ImportError) as error:
            # El CSV y el JSON ya están escritos; solo el gráfico se pierde.
            print(f"no se pudo graficar: {error}", file=sys.stderr)
            return ESCENARIO_INVALIDO
    return OK


if __name__ == "__main__":
    sys.exit(main())
