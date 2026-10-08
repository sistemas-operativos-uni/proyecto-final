# Selecciona para reemplazo la página menos recientemente utilizada.

def seleccionar_victima_lru(
    orden_uso: list[int],
    paginas_residentes: list[int],
) -> int:
    for pagina in orden_uso:
        if pagina in paginas_residentes:
            return pagina

    raise ValueError("No hay páginas residentes para reemplazar.")