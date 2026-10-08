# Registra marcos físicos libres, ocupados y la página residente en cada marco.

class GestorMarcos:
    def __init__(self, cantidad_marcos: int) -> None:
        if cantidad_marcos <= 0:
            raise ValueError("La cantidad de marcos debe ser mayor que cero.")

        self.marcos: list[int | None] = [None] * cantidad_marcos

    def buscar_pagina(self, pagina: int) -> int | None:
        for numero_marco, pagina_actual in enumerate(self.marcos):
            if pagina_actual == pagina:
                return numero_marco

        return None

    def buscar_marco_libre(self) -> int | None:
        for numero_marco, pagina_actual in enumerate(self.marcos):
            if pagina_actual is None:
                return numero_marco

        return None

    def cargar_pagina(self, numero_marco: int, pagina: int) -> None:
        if not 0 <= numero_marco < len(self.marcos):
            raise IndexError("El número de marco está fuera de rango.")

        self.marcos[numero_marco] = pagina

    def reemplazar_pagina(self, numero_marco: int, pagina: int) -> int | None:
        if not 0 <= numero_marco < len(self.marcos):
            raise IndexError("El número de marco está fuera de rango.")

        pagina_anterior = self.marcos[numero_marco]
        self.marcos[numero_marco] = pagina

        return pagina_anterior