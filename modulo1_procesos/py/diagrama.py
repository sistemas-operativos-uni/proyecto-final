"""Presentación de un resultado de planificación: Gantt ASCII, log e informe.

Es la única capa del módulo que arma texto. Los algoritmos devuelven datos y
estas funciones los formatean, así que cambiar el aspecto del log no toca
ninguna regla de planificación.
"""

from __future__ import annotations

from core.metricas import formatear_tabla

from .motor import (
    ACCION_CAMBIO_CONTEXTO,
    ACCION_EXPROPIACION,
    ACCION_OCIOSA,
    ResultadoPlanificacion,
    Segmento,
)
from .pcb import ACCION_TRANSICION

PREFIJO_GANTT = "Gantt: "
ETIQUETA_OCIOSA = "ocio"
ETIQUETA_CAMBIO_CONTEXTO = "ctx"
CARACTERES_POR_UNIDAD = 2
COLUMNAS_TABLA = ("pid", "llegada", "rafaga", "prioridad", "inicio", "fin", "espera", "retorno", "respuesta")


def gantt_ascii(segmentos: tuple[Segmento, ...]) -> str:
    """Dibuja la línea de tiempo de la CPU en dos filas.

    La primera fila lleva un bloque por segmento; la segunda, el instante en
    que empieza cada bloque bajo su barra `|`. Un bloque mide dos caracteres
    por unidad de tiempo, así el ancho se parece a la duración.
    """
    if not segmentos:
        return f"{PREFIJO_GANTT}(sin procesos)"

    barra = ""
    marcas: list[tuple[int, str]] = []  # (columna, texto) de la fila de tiempos
    columna = 0
    for segmento in segmentos:
        etiqueta = segmento.pid or (
            ETIQUETA_CAMBIO_CONTEXTO if segmento.cambio_contexto else ETIQUETA_OCIOSA
        )
        # El ancho nunca baja de lo que ocupan el nombre y el número de tiempo
        # que va debajo; sin ese mínimo, "P001" no cabría en una ráfaga de 1
        # y dos marcas de tiempo se pisarían.
        ancho = max(
            CARACTERES_POR_UNIDAD * (segmento.fin - segmento.inicio),
            len(etiqueta),
            len(str(segmento.inicio)) + 1,
        )
        marcas.append((columna, str(segmento.inicio)))
        barra += "|" + etiqueta.ljust(ancho)
        columna += 1 + ancho
    barra += "|"
    marcas.append((columna, str(segmentos[-1].fin)))

    tiempos = ""
    for posicion, texto in marcas:
        tiempos = tiempos.ljust(posicion) + texto
    return f"{PREFIJO_GANTT}{barra}\n{' ' * len(PREFIJO_GANTT)}{tiempos}"


def lineas_de_log(resultado: ResultadoPlanificacion) -> list[str]:
    """Una línea por evento, en el orden en que ocurrieron."""
    por_pid = {p.pid: p for p in resultado.procesos}
    lineas = []
    for evento in resultado.eventos:
        base = f"[modulo1][t={evento.instante:03d}] {resultado.algoritmo}  {evento.entidad}  "
        if evento.accion == ACCION_OCIOSA:
            lineas.append(f"{base}OCIOSA hasta t={evento.datos['hasta']}")
            continue
        if evento.accion == ACCION_CAMBIO_CONTEXTO:
            datos = evento.datos
            lineas.append(f"{base}CAMBIO_CONTEXTO {datos['de']} -> {datos['a']} (costo={datos['costo']})")
            continue
        if evento.accion == ACCION_EXPROPIACION:
            cola = ",".join(evento.datos["cola"])
            lineas.append(f"{base}EXPROPIADO (restante={evento.datos['restante']}) -> cola=[{cola}]")
            continue
        if evento.accion != ACCION_TRANSICION:
            continue  # un evento de otro tipo no tiene formato definido
        if evento.datos["desde"] == "EJECUCION" and evento.datos["hacia"] == "LISTO":
            # Toda expropiación trae su propio evento EXPROPIACION, que además
            # muestra la cola. Imprimir también la transición repetiría la línea.
            continue
        linea = f"{base}{evento.datos['desde']} -> {evento.datos['hacia']}"
        # La espera se anota solo en el primer despacho. Un despacho posterior
        # (Round Robin) no tendría una única "espera" que mostrar.
        proceso = por_pid.get(evento.entidad)
        if evento.datos["hacia"] == "EJECUCION" and proceso and evento.instante == proceso.inicio:
            linea += f"  (espera={evento.instante - proceso.llegada})"
        lineas.append(linea)
    return lineas


def _formato_media(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:.2f}"


def informe(
    resultado: ResultadoPlanificacion, escenario: str | None = None, verbose: bool = False
) -> str:
    """Texto completo de un algoritmo: encabezado, Gantt, tabla y medias.

    Con `verbose` agrega el log por evento al final.
    """
    titulo = f"== {resultado.algoritmo} | escenario={escenario} ==" if escenario else f"== {resultado.algoritmo} =="
    filas = [{columna: getattr(p, columna) for columna in COLUMNAS_TABLA} for p in resultado.procesos]
    partes = [
        titulo,
        gantt_ascii(resultado.segmentos),
        formatear_tabla(COLUMNAS_TABLA, filas),
        f"espera media={_formato_media(resultado.espera_media)} "
        f"retorno medio={_formato_media(resultado.retorno_medio)} "
        f"cambios de contexto={resultado.cambios_contexto}",
    ]
    if verbose:
        partes.append("\n".join(lineas_de_log(resultado)))
    return "\n".join(partes)
