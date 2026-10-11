"""Punto de entrada de SO-Sim.

Cada subcomando corresponde a una etapa del simulador:

    python main.py cargar [--escenario RUTA]   valida un escenario y lo muestra
    python main.py procesos [--escenario RUTA] [--algoritmo A] [--quantum N]
                            [--cambio-contexto N] [--exportar] [--resultados DIR]
                                               Módulo 1: planificación de CPU

Códigos de salida: 0 todo bien, 1 escenario inválido o resultado con errores,
2 uso incorrecto. Solo esta capa escribe en consola; los módulos devuelven datos.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from core.cargador_escenarios import ErrorEscenario, cargar_procesos
from core.metricas import formatear_tabla
from core.modelos import COMPLETADO, SimulationConfig
from modulo1_procesos.py.adaptador import ModuloProcesos
from modulo1_procesos.py.diagrama import informe_modulo
from modulo1_procesos.py.planificador import ALGORITMOS, validos

OK = 0
ESCENARIO_INVALIDO = 1
USO_INCORRECTO = 2

# Se resuelve junto a main.py y no junto al directorio de trabajo: así el
# comando funciona igual desde la raíz, desde `make` o desde otra carpeta.
ESCENARIO_POR_DEFECTO = Path(__file__).resolve().parent / "escenarios" / "lote_pequeno.csv"

RESULTADOS_POR_DEFECTO = Path(__file__).resolve().parent / "resultados"
TODOS = "todos"

COLUMNAS_PROCESO = ("id", "llegada", "rafaga", "prioridad", "memoria_kb", "cursos")


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="SO-Sim: simulador educativo de un SO.")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    cargar = subcomandos.add_parser("cargar", help="valida un escenario CSV y muestra sus procesos")
    cargar.add_argument(
        "--escenario",
        type=Path,
        default=ESCENARIO_POR_DEFECTO,
        help="ruta del CSV (por defecto escenarios/lote_pequeno.csv)",
    )

    procesos = subcomandos.add_parser("procesos", help="planificación de procesos (Módulo 1)")
    procesos.add_argument("--escenario", type=Path, default=ESCENARIO_POR_DEFECTO, help="CSV de procesos")
    procesos.add_argument("--algoritmo", default=TODOS, help=f"{validos()} o todos (por defecto)")
    procesos.add_argument("--quantum", type=int, default=2, help="quantum de Round Robin (por defecto 2)")
    procesos.add_argument(
        "--cambio-contexto", type=int, default=0, dest="cambio_contexto", help="coste de cada cambio de contexto"
    )
    procesos.add_argument("--exportar", action="store_true", help="guarda la comparación en CSV, JSON y un gráfico PNG")
    procesos.add_argument("--resultados", type=Path, default=RESULTADOS_POR_DEFECTO, help="carpeta de exportación")
    return parser


def _comando_cargar(escenario: Path) -> int:
    # Se usa la versión estricta: si una fila falla, el escenario no se
    # simula y el usuario ve todos los errores juntos, nunca un "OK" parcial.
    try:
        procesos = cargar_procesos(escenario)
    except ErrorEscenario as error:
        print(f"[core] escenario={escenario.name} validación=ERROR", file=sys.stderr)
        print(error, file=sys.stderr)
        return ESCENARIO_INVALIDO

    print(f"[core] escenario={escenario.name} procesos={len(procesos)} validación=OK")
    filas = [
        {
            "id": p.id,
            "llegada": p.llegada,
            "rafaga": p.rafaga,
            "prioridad": p.prioridad,
            "memoria_kb": p.memoria_kb,
            "cursos": ";".join(p.cursos),
        }
        for p in procesos
    ]
    print(formatear_tabla(COLUMNAS_PROCESO, filas))
    return OK


def _comando_procesos(argumentos: argparse.Namespace) -> int:
    # Los errores de uso se rechazan aquí, con código 2, antes de llamar al
    # módulo. Un escenario malo es otra cosa: llega al adaptador, que lo deja
    # en `ModuleResult.errores`, y esta capa lo muestra.
    elegido = argumentos.algoritmo.strip().lower()
    if elegido != TODOS and elegido.upper() not in ALGORITMOS:
        print(f"algoritmo desconocido {argumentos.algoritmo!r}; válidos: {validos()}", file=sys.stderr)
        return USO_INCORRECTO
    if argumentos.exportar and elegido != TODOS:
        print("--exportar compara algoritmos: use --algoritmo todos", file=sys.stderr)
        return USO_INCORRECTO
    try:
        config = SimulationConfig(
            escenario=argumentos.escenario,
            algoritmo=argumentos.algoritmo,
            quantum=argumentos.quantum,
            cambio_contexto=argumentos.cambio_contexto,
            directorio_resultados=argumentos.resultados,
            exportar=argumentos.exportar,
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        return USO_INCORRECTO

    resultado = ModuloProcesos().ejecutar(config)

    print(informe_modulo(resultado))
    exportado = resultado.metricas.get("exportado")
    if exportado:
        archivos = [exportado["csv"], exportado["json"], *([exportado["grafico"]] if "grafico" in exportado else [])]
        print(f"[modulo1] exportado: {', '.join(archivos)}")
    # Cada error sale por la salida de error, uno por línea. Un resultado con
    # errores nunca termina en silencio ni con código 0.
    for error in resultado.errores:
        print(f"[modulo1] error: {error}", file=sys.stderr)
    return OK if resultado.estado == COMPLETADO else ESCENARIO_INVALIDO


def main(argv: Sequence[str] | None = None) -> int:
    """Interpreta `argv`, ejecuta el subcomando y devuelve el código de salida."""
    try:
        argumentos = _crear_parser().parse_args(argv)
    except SystemExit as salida:
        # argparse termina el proceso ante un uso incorrecto. Se captura para
        # que `main` siempre devuelva un código y las pruebas puedan leerlo.
        return int(salida.code or 0)

    if argumentos.comando == "cargar":
        return _comando_cargar(argumentos.escenario)
    return _comando_procesos(argumentos)


if __name__ == "__main__":
    sys.exit(main())
