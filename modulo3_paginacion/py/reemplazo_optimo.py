# Simula reemplazo óptimo usando referencias futuras conocidas en la traza.

def seleccionar_victima_optimo(
    referencias_futuras: list[int],
    paginas_residentes: list[int],
) -> int:
    if not paginas_residentes:
        raise ValueError("No hay páginas residentes para reemplazar.")

    for pagina in paginas_residentes:
        if pagina not in referencias_futuras:
            return pagina

    distancias = {
        pagina: referencias_futuras.index(pagina)
        for pagina in paginas_residentes
    }

    return max(distancias, key=distancias.get)