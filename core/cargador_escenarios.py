"""Carga de escenarios CSV: lee procesos y reporta cada fila inválida.

Hay dos versiones. La tolerante devuelve las filas válidas y un mensaje por
cada fila rechazada, para que la interfaz muestre todo de una vez. La estricta
lanza ErrorEscenario si el escenario tiene cualquier defecto.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from core.modelos import Proceso

COLUMNAS_OBLIGATORIAS = ("id", "llegada", "rafaga", "prioridad", "memoria_kb", "cursos")
_COLUMNAS_ENTERAS = ("llegada", "rafaga", "prioridad", "memoria_kb")


class ErrorEscenario(Exception):
    """El escenario no se puede usar: falla el archivo o no queda ningún proceso."""


@dataclass(frozen=True, slots=True)
class CargaProcesos:
    procesos: tuple[Proceso, ...]
    errores: tuple[str, ...]


def cargar_procesos_tolerante(ruta: str | Path) -> CargaProcesos:
    """Devuelve las filas válidas y un mensaje 'línea N: motivo' por cada inválida."""
    registros = csv.reader(io.StringIO(_leer_texto(Path(ruta)), newline=""))

    # La cabecera se valida antes que las filas: sin ella no se sabe qué
    # significa cada columna, y cada fila repetiría el mismo mensaje.
    cabecera = [nombre.strip() for nombre in next(registros, [])]
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in cabecera]
    if faltan:
        raise ErrorEscenario(f"la cabecera no tiene las columnas: {', '.join(faltan)}")
    posicion = {nombre: i for i, nombre in enumerate(cabecera)}

    procesos: list[Proceso] = []
    errores: list[str] = []
    ids_vistos: set[str] = set()
    ultima_linea = registros.line_num
    for fila in registros:
        # csv.reader cuenta líneas físicas y un campo entre comillas puede
        # ocupar varias, así que la fila empieza donde terminó la anterior.
        linea = ultima_linea + 1
        ultima_linea = registros.line_num
        if not fila:
            continue
        try:
            proceso = _fila_a_proceso(fila, len(cabecera), posicion)
            # Regla del id duplicado: gana la primera aparición y la repetida
            # se rechaza, porque el planificador identifica procesos por id.
            if proceso.id in ids_vistos:
                raise ValueError(f"id duplicado {proceso.id!r}")
        except ValueError as error:
            errores.append(f"línea {linea}: {error}")
            continue
        ids_vistos.add(proceso.id)
        procesos.append(proceso)
    return CargaProcesos(tuple(procesos), tuple(errores))


def cargar_procesos(ruta: str | Path) -> tuple[Proceso, ...]:
    """Versión estricta: lanza ErrorEscenario si hay algún error o ningún proceso."""
    # Se apoya en la tolerante para que ambas versiones apliquen las mismas
    # reglas y la estricta pueda informar todos los errores juntos.
    carga = cargar_procesos_tolerante(ruta)
    if carga.errores:
        raise ErrorEscenario("\n".join(carga.errores))
    if not carga.procesos:
        raise ErrorEscenario(f"el escenario no contiene ningún proceso: {ruta}")
    return carga.procesos


def _fila_a_proceso(fila: list[str], esperadas: int, posicion: dict[str, int]) -> Proceso:
    if len(fila) != esperadas:
        raise ValueError(f"se esperaban {esperadas} columnas y hay {len(fila)}")
    enteros = {c: _entero(c, fila[posicion[c]]) for c in _COLUMNAS_ENTERAS}
    cursos = tuple(c.strip() for c in fila[posicion["cursos"]].split(";") if c.strip())
    return Proceso(id=fila[posicion["id"]].strip(), cursos=cursos, **enteros)


def _entero(columna: str, valor: str) -> int:
    try:
        return int(valor.strip())
    except ValueError:
        raise ValueError(f"{columna} debe ser un entero, recibió {valor!r}") from None


def _leer_texto(ruta: Path) -> str:
    try:
        # utf-8-sig descarta el BOM que Excel añade al guardar como CSV UTF-8.
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            texto = archivo.read()
    except FileNotFoundError:
        raise ErrorEscenario(f"el archivo no existe: {ruta}") from None
    except UnicodeDecodeError:
        raise ErrorEscenario(f"el archivo no está en UTF-8: {ruta}") from None
    except OSError as error:
        raise ErrorEscenario(f"no se pudo leer {ruta}: {error.strerror or error}") from error
    if not texto.strip():
        raise ErrorEscenario(f"el archivo está vacío: {ruta}")
    return texto
