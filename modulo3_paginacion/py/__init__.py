# Paginación virtual, administración de marcos y políticas de reemplazo.

from .gestor_paginacion import GestorPaginacion
from .marcos import GestorMarcos
from .paginacion import dividir_direccion_logica, traducir_direccion
from .reemplazo_fifo import seleccionar_victima_fifo
from .reemplazo_lru import seleccionar_victima_lru
from .reemplazo_optimo import seleccionar_victima_optimo

__all__ = [
    "GestorPaginacion",
    "GestorMarcos",
    "dividir_direccion_logica",
    "traducir_direccion",
    "seleccionar_victima_fifo",
    "seleccionar_victima_lru",
    "seleccionar_victima_optimo",
]