"""Reloj lógico compartido para ordenar los eventos de una simulación.

El tiempo se mide en unidades enteras, sin relación con el reloj de pared.
Solo avanza: ningún módulo puede retroceder el instante de otro.
"""

from __future__ import annotations


def _exigir_entero(nombre: str, valor: object, minimo: int) -> None:
    # bool hereda de int en Python; True no cuenta como entero válido aquí.
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{nombre} debe ser un entero, recibió {valor!r}")
    if valor < minimo:
        raise ValueError(f"{nombre} debe ser >= {minimo}, recibió {valor}")


class RelojLogico:
    """Instante actual de la simulación.

    La monotonía es la regla central: los eventos se ordenan por instante, y un
    reloj que retrocede dejaría eventos fuera de orden en la línea de tiempo.
    """

    __slots__ = ("_ahora",)

    def __init__(self, inicio: int = 0) -> None:
        _exigir_entero("inicio", inicio, 0)
        self._ahora = inicio

    @property
    def ahora(self) -> int:
        return self._ahora

    def avanzar(self, unidades: int = 1) -> int:
        """Suma `unidades` al instante y devuelve el nuevo valor.

        Acepta 0 para que un llamador pueda avanzar "lo que haya pasado" sin
        tratar el caso vacío aparte.
        """
        _exigir_entero("unidades", unidades, 0)
        self._ahora += unidades
        return self._ahora

    def saltar_a(self, instante: int) -> int:
        """Lleva el reloj a `instante` y lo devuelve.

        El planificador salta a la siguiente llegada cuando la CPU está ociosa,
        en lugar de avanzar de unidad en unidad por un tramo sin trabajo.
        """
        # La validación va antes de asignar: si falla, el reloj conserva su
        # instante y la simulación puede seguir con un estado consistente.
        _exigir_entero("instante", instante, self._ahora)
        self._ahora = instante
        return self._ahora

    def __repr__(self) -> str:
        return f"RelojLogico(ahora={self._ahora})"
