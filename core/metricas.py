"""Reúne y exporta métricas comunes producidas por los módulos.

Ofrece el promedio que todos los algoritmos necesitan, la exportación a CSV y
JSON para la carpeta de resultados y una tabla de texto para la consola. Solo
usa la biblioteca estándar; las gráficas viven en otro lugar.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

# Texto que se muestra en la tabla cuando una fila no trae la clave.
AUSENTE = "-"


def _es_numero(valor: object) -> bool:
    # bool hereda de int; True no cuenta como métrica numérica.
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def promedio(valores: Iterable[float]) -> float:
    """Media aritmética de ints y floats."""
    lista = list(valores)
    # Un promedio sin datos delata un error aguas arriba (por ejemplo, un lote
    # sin procesos terminados). Devolver 0 lo escondería dentro de las métricas.
    if not lista:
        raise ValueError("promedio no puede calcularse sobre una secuencia vacía")
    for valor in lista:
        if not _es_numero(valor):
            raise ValueError(f"promedio solo acepta números, recibió {valor!r}")
    return sum(lista) / len(lista)


def _preparar_ruta(ruta: str | Path) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    return destino


def exportar_csv(
    filas: Sequence[Mapping[str, object]],
    ruta: str | Path,
    columnas: Sequence[str] | None = None,
) -> Path:
    """Escribe cabecera y filas en UTF-8 y devuelve la ruta escrita."""
    if columnas is None:
        # El orden de las claves de la primera fila fija el orden de las
        # columnas; así el CSV sale igual que el diccionario que lo produjo.
        columnas = list(filas[0]) if filas else []
    if not columnas:
        raise ValueError("exportar_csv necesita filas o columnas para la cabecera")

    destino = _preparar_ruta(ruta)
    # newline="" deja que el módulo csv controle los saltos de línea.
    with destino.open("w", encoding="utf-8", newline="") as archivo:
        # restval rellena las claves ausentes; extrasaction ignora las que
        # no están en columnas.
        escritor = csv.DictWriter(
            archivo, fieldnames=list(columnas), restval="", extrasaction="ignore"
        )
        escritor.writeheader()
        escritor.writerows(filas)
    return destino


def exportar_json(datos: object, ruta: str | Path) -> Path:
    """Escribe `datos` como JSON legible y devuelve la ruta escrita."""
    # Se serializa antes de abrir el archivo: si `datos` no es serializable,
    # json lanza TypeError sin haber tocado el disco y no queda un archivo
    # cortado a la mitad ni se pisa uno previo.
    texto = json.dumps(datos, indent=2, ensure_ascii=False) + "\n"
    destino = _preparar_ruta(ruta)
    destino.write_text(texto, encoding="utf-8")
    return destino


def _celda(valor: object, con_decimales: bool) -> str:
    if con_decimales and _es_numero(valor):
        return f"{valor:.2f}"
    return str(valor)


def formatear_tabla(
    columnas: Sequence[str], filas: Sequence[Mapping[str, object]]
) -> str:
    """Tabla de texto para consola con columnas alineadas."""
    if not columnas:
        raise ValueError("formatear_tabla necesita al menos una columna")

    # Una columna con algún float muestra todos sus números con 2 decimales,
    # así un 8 junto a un 9.5 se lee 8.00 y los puntos decimales coinciden.
    con_decimales = [
        any(isinstance(f.get(c), float) for f in filas) for c in columnas
    ]
    textos = [
        [
            AUSENTE if c not in fila else _celda(fila[c], con_decimales[i])
            for i, c in enumerate(columnas)
        ]
        for fila in filas
    ]

    lineas = []
    anchos = []
    a_la_derecha = []
    for i, nombre in enumerate(columnas):
        presentes = [fila[nombre] for fila in filas if nombre in fila]
        # Regla de alineación: una columna es numérica si todos sus valores
        # presentes son números. Esas columnas, con su cabecera y los guiones
        # de clave ausente, van a la derecha para que los decimales coincidan;
        # el resto va a la izquierda.
        a_la_derecha.append(bool(presentes) and all(_es_numero(v) for v in presentes))
        anchos.append(max([len(nombre)] + [len(fila[i]) for fila in textos]))

    def armar(celdas: Sequence[str]) -> str:
        partes = [
            c.rjust(anchos[i]) if a_la_derecha[i] else c.ljust(anchos[i])
            for i, c in enumerate(celdas)
        ]
        # rstrip evita espacios sobrantes tras una última columna de texto.
        return "  ".join(partes).rstrip()

    lineas.append(armar(columnas))
    lineas.append("  ".join("-" * ancho for ancho in anchos))
    lineas.extend(armar(fila) for fila in textos)
    return "\n".join(lineas)
