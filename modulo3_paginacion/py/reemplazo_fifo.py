# Selecciona para reemplazo la página que lleva más tiempo en memoria.

def seleccionar_victima_fifo(
    orden_carga: list[int],
    paginas_residentes: list[int],
) -> int:
    for pagina in orden_carga:
        if pagina in paginas_residentes:
            return pagina

    raise ValueError("No hay páginas residentes para reemplazar.")