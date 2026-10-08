"""Funciones para la traducción de direcciones mediante paginación."""

def dividir_direccion_logica(direccion: int, tamano_pagina: int) -> tuple[int, int]:
    if direccion < 0:
        raise ValueError("La dirección lógica no puede ser negativa.")

    if tamano_pagina <= 0:
        raise ValueError("El tamaño de página debe ser mayor que cero.")

    numero_pagina = direccion // tamano_pagina
    desplazamiento = direccion % tamano_pagina

    return numero_pagina, desplazamiento

def traducir_direccion(
    direccion: int,
    tamano_pagina: int,
    tabla_paginas: dict[int, int],
) -> int:
    numero_pagina, desplazamiento = dividir_direccion_logica(
        direccion,
        tamano_pagina,
    )

    if numero_pagina not in tabla_paginas:
        raise KeyError(f"La página {numero_pagina} no está en la tabla de páginas.")

    numero_marco = tabla_paginas[numero_pagina]

    return numero_marco * tamano_pagina + desplazamiento
