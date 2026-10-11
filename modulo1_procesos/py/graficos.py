"""Gráfico de barras de la comparación de algoritmos.

Muestra la espera media y el retorno medio de cada algoritmo, con el valor
sobre cada barra. Se guarda como `procesos_<escenario>.png`.

El dibujo usa el backend Agg: escribe píxeles a un búfer en memoria y no abre
ninguna ventana. Se arma con `Figure` y `FigureCanvasAgg` en lugar de `pyplot`
a propósito. `pyplot` elige un backend global al importarse y, en una máquina
sin pantalla, uno de ventana (TkAgg, por ejemplo) falla. Con las clases
directas no hay estado global y el resultado no depende del entorno.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from .metricas_planificacion import ComparacionAlgoritmos

if TYPE_CHECKING:  # solo para anotar el tipo; no se importa al ejecutar
    from matplotlib.figure import Figure

ANCHO_PULGADAS = 8
ALTO_PULGADAS = 4.5
PUNTOS_POR_PULGADA = 100  # 8 x 4.5 pulgadas dan un PNG de 800 x 450 píxeles
ANCHO_BARRA = 0.38
ETIQUETA_ESPERA = "Espera media"
ETIQUETA_RETORNO = "Retorno medio"
ETIQUETA_EJE_Y = "Unidades de tiempo"

# Azul y naranja: se distinguen para daltonismo común y también en escala de grises.
COLOR_ESPERA = "#4C72B0"
COLOR_RETORNO = "#DD8452"


def construir_figura(comparacion: ComparacionAlgoritmos, escenario: str | None = None) -> Figure:
    """Arma la figura sin guardarla. Separarla del guardado permite inspeccionarla."""
    # matplotlib se importa aquí, no al cargar el módulo. Así el resto del
    # Módulo 1 funciona en una instalación que no lo tenga, y solo graficar falla.
    from matplotlib.figure import Figure

    nombres = list(comparacion.nombres)
    esperas = [m.espera_media for m in comparacion.metricas]
    retornos = [m.retorno_medio for m in comparacion.metricas]
    # Sin procesos las medias valen None. Una figura con barras de altura cero
    # parecería un resultado y sería un escenario vacío: se rechaza.
    if not nombres or any(v is None for v in esperas + retornos):
        raise ValueError("no hay datos que graficar: el escenario no tiene procesos")

    figura = Figure(figsize=(ANCHO_PULGADAS, ALTO_PULGADAS), dpi=PUNTOS_POR_PULGADA, layout="constrained")
    ejes = figura.subplots()

    # Cada algoritmo ocupa una posición del eje; sus dos barras se reparten a
    # ambos lados del centro para quedar juntas y comparables.
    centros = list(range(len(nombres)))
    barras_espera = ejes.bar(
        [c - ANCHO_BARRA / 2 for c in centros], esperas, ANCHO_BARRA, label=ETIQUETA_ESPERA, color=COLOR_ESPERA
    )
    barras_retorno = ejes.bar(
        [c + ANCHO_BARRA / 2 for c in centros], retornos, ANCHO_BARRA, label=ETIQUETA_RETORNO, color=COLOR_RETORNO
    )
    ejes.bar_label(barras_espera, fmt="%.2f", padding=2, fontsize=8)
    ejes.bar_label(barras_retorno, fmt="%.2f", padding=2, fontsize=8)

    ejes.set_xticks(centros, nombres)
    ejes.set_ylabel(ETIQUETA_EJE_Y)
    ejes.set_title(f"Espera y retorno medios | {escenario}" if escenario else "Espera y retorno medios")
    ejes.legend()
    ejes.set_axisbelow(True)  # la cuadrícula va detrás de las barras
    ejes.yaxis.grid(True, alpha=0.3)
    return figura


def graficar_comparacion(
    comparacion: ComparacionAlgoritmos, escenario: str | Path, directorio: str | Path = "resultados"
) -> Path:
    """Guarda `procesos_<escenario>.png` en `directorio` y devuelve su ruta.

    El nombre sale del escenario sin carpeta ni extensión, igual que el CSV y
    el JSON de `exportar_comparacion`.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    nombre = Path(escenario).stem
    figura = construir_figura(comparacion, Path(escenario).name)  # falla antes de crear nada si no hay datos
    FigureCanvasAgg(figura)  # fija Agg como el canvas de esta figura

    # Se dibuja a un búfer y solo después se escribe el archivo: si el dibujo
    # falla no queda un PNG a medias. `Software: None` quita la versión de
    # matplotlib de los metadatos, para que dos corridas den los mismos bytes.
    buffer = io.BytesIO()
    figura.savefig(buffer, format="png", metadata={"Software": None})

    destino = Path(directorio)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"procesos_{nombre}.png"
    ruta.write_bytes(buffer.getvalue())
    return ruta
