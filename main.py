"""Punto de entrada de SO-Sim.

Cada subcomando corresponde a una etapa del simulador:

    python main.py cargar [--escenario RUTA]   valida un escenario y lo muestra
    python main.py procesos                    Módulo 1 (disponible en la Fase 7)

Códigos de salida: 0 todo bien, 1 escenario inválido, 2 uso incorrecto o
subcomando que aún no existe. Solo esta capa escribe en consola; los módulos
devuelven datos.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from core.cargador_escenarios import ErrorEscenario, cargar_procesos
from core.metricas import formatear_tabla

OK = 0
ESCENARIO_INVALIDO = 1
USO_INCORRECTO = 2

# Se resuelve junto a main.py y no junto al directorio de trabajo: así el
# comando funciona igual desde la raíz, desde `make` o desde otra carpeta.
ESCENARIO_POR_DEFECTO = Path(__file__).resolve().parent / "escenarios" / "lote_pequeno.csv"

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

    subcomandos.add_parser("procesos", help="planificación de procesos (Módulo 1)")
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


def _comando_procesos() -> int:
    # Marcador explícito: el Módulo 1 se conecta en la Fase 7 del WORKPLAN.
    # Devolver 2 evita que un script crea que la simulación corrió.
    print("[modulo1] subcomando 'procesos' no implementado todavía (Fase 7 del WORKPLAN)", file=sys.stderr)
    return USO_INCORRECTO


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
    return _comando_procesos()


if __name__ == "__main__":
    sys.exit(main())
