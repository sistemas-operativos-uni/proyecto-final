# Coordina traducción, fallos de página, marcos y política de reemplazo.

from .marcos import GestorMarcos
from .reemplazo_fifo import seleccionar_victima_fifo
from .reemplazo_lru import seleccionar_victima_lru
from .reemplazo_optimo import seleccionar_victima_optimo

class GestorPaginacion:

    def __init__(
        self,
        cantidad_marcos: int,
        politica: str,
    ) -> None:
        if politica not in {"FIFO", "LRU", "OPTIMO"}:
            raise ValueError(
                "La política debe ser FIFO, LRU u OPTIMO."
            )

        self.marcos = GestorMarcos(cantidad_marcos)
        self.politica = politica
        self.fallos_pagina = 0
        self.orden_carga: list[int] = []
        self.orden_uso: list[int] = []
        self.eventos: list[dict] = []

    def procesar_referencia(
        self,
        pagina: int,
        referencias_futuras: list[int] | None = None,
    ) -> bool:

        marco = self.marcos.buscar_pagina(pagina)

        if marco is not None:
            self._registrar_uso(pagina)
            self.eventos.append(
                {
                    "pagina": pagina,
                    "tipo": "acierto",
                    "marco": marco,
                }
            )
            return False

        self.fallos_pagina += 1

        marco_libre = self.marcos.buscar_marco_libre()

        if marco_libre is not None:
            self.marcos.cargar_pagina(marco_libre, pagina)
            self.orden_carga.append(pagina)
            self._registrar_uso(pagina)

            self.eventos.append(
                {
                    "pagina": pagina,
                    "tipo": "fallo",
                    "accion": "cargar",
                    "marco": marco_libre,
                }
            )
            return True

        paginas_residentes = [
            pagina_residente
            for pagina_residente in self.marcos.marcos
            if pagina_residente is not None
        ]

        if self.politica == "FIFO":
            victima = seleccionar_victima_fifo(
                self.orden_carga,
                paginas_residentes,
            )
        elif self.politica == "LRU":
            victima = seleccionar_victima_lru(
                self.orden_uso,
                paginas_residentes,
            )
        else:
            victima = seleccionar_victima_optimo(
                referencias_futuras or [],
                paginas_residentes,
            )

        marco_victima = self.marcos.buscar_pagina(victima)

        if marco_victima is None:
            raise RuntimeError("No se encontró el marco de la página víctima.")

        self.marcos.reemplazar_pagina(marco_victima, pagina)

        if victima in self.orden_carga:
            self.orden_carga.remove(victima)

        self.orden_carga.append(pagina)
        self._registrar_uso(pagina)

        self.eventos.append(
            {
                "pagina": pagina,
                "tipo": "fallo",
                "accion": "reemplazar",
                "pagina_expulsada": victima,
                "marco": marco_victima,
            }
        )

        return True

    def _registrar_uso(self, pagina: int) -> None:
        if pagina in self.orden_uso:
            self.orden_uso.remove(pagina)

        self.orden_uso.append(pagina)

    def simular(self, referencias: list[int]) -> dict:
        for indice, pagina in enumerate(referencias):
            referencias_futuras = referencias[indice + 1 :]

            self.procesar_referencia(
                pagina,
                referencias_futuras,
            )

        return {
            "politica": self.politica,
            "fallos_pagina": self.fallos_pagina,
            "marcos_finales": self.marcos.marcos.copy(),
            "eventos": self.eventos.copy(),
        }