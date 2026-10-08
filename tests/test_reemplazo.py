# Pruebas para FIFO, LRU y Óptimo sobre la misma traza.

from modulo3_paginacion.py.reemplazo_fifo import seleccionar_victima_fifo
from modulo3_paginacion.py.reemplazo_lru import seleccionar_victima_lru
from modulo3_paginacion.py.reemplazo_optimo import seleccionar_victima_optimo
from modulo3_paginacion.py.gestor_paginacion import GestorPaginacion

def test_fifo_selecciona_pagina_mas_antigua() -> None:
    assert seleccionar_victima_fifo(
        [2, 5, 1],
        [5, 1],
    ) == 5

def test_lru_selecciona_pagina_menos_reciente() -> None:
    assert seleccionar_victima_lru(
        [2, 5, 1],
        [5, 1],
    ) == 5

def test_optimo_selecciona_pagina_con_uso_mas_lejano() -> None:
    assert seleccionar_victima_optimo(
        [1, 2, 3, 4],
        [2, 3],
    ) == 3

REFERENCIAS = [2, 5, 2, 1, 5, 3, 1, 2, 4, 1]

def test_gestor_fifo() -> None:
    gestor = GestorPaginacion(3, "FIFO")
    resultado = gestor.simular(REFERENCIAS)

    assert resultado["fallos_pagina"] == 7

def test_gestor_lru() -> None:
    gestor = GestorPaginacion(3, "LRU")
    resultado = gestor.simular(REFERENCIAS)

    assert resultado["fallos_pagina"] == 6

def test_gestor_optimo() -> None:
    gestor = GestorPaginacion(3, "OPTIMO")
    resultado = gestor.simular(REFERENCIAS)

    assert resultado["fallos_pagina"] == 5