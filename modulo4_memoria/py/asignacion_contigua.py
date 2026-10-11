"""Asigna y libera bloques contiguos con primer, mejor y peor ajuste.

Modelo
------
La memoria es una fila de bloques consecutivos que cubren de 0 a
``total_kb``. Cada bloque está libre (un *hueco*) o pertenece a un proceso.
Al iniciar hay un solo hueco del tamaño de toda la memoria.

Asignar un proceso consiste en:

1. redondear lo pedido hacia arriba a la unidad de asignación
   (por ejemplo, 96 KB con unidad de 64 KB ocupa 128 KB);
2. elegir un hueco donde quepa, según la estrategia;
3. partir ese hueco: el comienzo pasa al proceso y el resto sigue libre.

Liberar devuelve el bloque al estado libre y lo fusiona con los huecos
vecinos, para que dos huecos contiguos no se cuenten como dos piezas.

Estrategias
-----------
- ``primer``: el primer hueco, de izquierda a derecha, donde quepa.
- ``mejor``: el hueco más pequeño donde quepa (deja el menor sobrante).
- ``peor``: el hueco más grande (deja el mayor sobrante).

Los empates se resuelven por la dirección más baja, así que una misma
entrada siempre produce el mismo mapa.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

PRIMER_AJUSTE = "primer"
MEJOR_AJUSTE = "mejor"
PEOR_AJUSTE = "peor"
ESTRATEGIAS = (PRIMER_AJUSTE, MEJOR_AJUSTE, PEOR_AJUSTE)


class ErrorMemoria(Exception):
    """Error recuperable de una operación de memoria."""


class SinEspacioError(ErrorMemoria):
    """Ningún hueco tiene el tamaño necesario.

    ``por_fragmentacion`` es ``True`` cuando la memoria libre total sí
    alcanzaba, pero estaba repartida en huecos demasiado pequeños: es el
    síntoma visible de la fragmentación externa.
    """

    def __init__(self, proceso_id: str, necesario_kb: int, libre_total_kb: int,
                 hueco_mayor_kb: int) -> None:
        self.proceso_id = proceso_id
        self.necesario_kb = necesario_kb
        self.libre_total_kb = libre_total_kb
        self.hueco_mayor_kb = hueco_mayor_kb
        self.por_fragmentacion = libre_total_kb >= necesario_kb
        causa = (
            "la memoria libre está fragmentada"
            if self.por_fragmentacion
            else "no hay memoria libre suficiente"
        )
        super().__init__(
            f"{proceso_id} necesita {necesario_kb} KB contiguos y el hueco mayor "
            f"es de {hueco_mayor_kb} KB ({libre_total_kb} KB libres en total): {causa}"
        )


@dataclass(frozen=True, slots=True)
class Bloque:
    """Tramo contiguo de memoria, libre u ocupado por un proceso.

    ``solicitado_kb`` es lo que pidió el proceso; ``tamano_kb`` es lo que
    recibió tras redondear a la unidad. La diferencia es fragmentación interna.
    """

    inicio_kb: int
    tamano_kb: int
    proceso_id: str | None = None
    solicitado_kb: int = 0

    @property
    def fin_kb(self) -> int:
        """Primera dirección que ya no pertenece al bloque."""

        return self.inicio_kb + self.tamano_kb

    @property
    def libre(self) -> bool:
        return self.proceso_id is None

    @property
    def desperdicio_kb(self) -> int:
        """Memoria asignada que el proceso no pidió (fragmentación interna)."""

        return 0 if self.libre else self.tamano_kb - self.solicitado_kb


SelectorHueco = Callable[[list[Bloque], int], Bloque | None]


def _primer_ajuste(huecos: list[Bloque], necesario_kb: int) -> Bloque | None:
    return next((h for h in huecos if h.tamano_kb >= necesario_kb), None)


def _mejor_ajuste(huecos: list[Bloque], necesario_kb: int) -> Bloque | None:
    candidatos = [h for h in huecos if h.tamano_kb >= necesario_kb]
    return min(candidatos, key=lambda h: (h.tamano_kb, h.inicio_kb), default=None)


def _peor_ajuste(huecos: list[Bloque], necesario_kb: int) -> Bloque | None:
    candidatos = [h for h in huecos if h.tamano_kb >= necesario_kb]
    return min(candidatos, key=lambda h: (-h.tamano_kb, h.inicio_kb), default=None)


SELECTORES: dict[str, SelectorHueco] = {
    PRIMER_AJUSTE: _primer_ajuste,
    MEJOR_AJUSTE: _mejor_ajuste,
    PEOR_AJUSTE: _peor_ajuste,
}


class MemoriaContigua:
    """Mapa de bloques contiguos con asignación y liberación.

    Invariantes que se mantienen después de cada operación:

    - los bloques están ordenados, son contiguos y cubren ``[0, total_kb)``;
    - no hay dos huecos seguidos (se fusionan al liberar);
    - cada proceso tiene como máximo un bloque.
    """

    def __init__(self, total_kb: int, unidad_kb: int = 1) -> None:
        if total_kb <= 0:
            raise ValueError("total_kb debe ser mayor que cero")
        if unidad_kb <= 0:
            raise ValueError("unidad_kb debe ser mayor que cero")
        if total_kb % unidad_kb:
            raise ValueError("total_kb debe ser múltiplo de unidad_kb")
        self.total_kb = total_kb
        self.unidad_kb = unidad_kb
        self._bloques: list[Bloque] = [Bloque(0, total_kb)]

    @property
    def bloques(self) -> tuple[Bloque, ...]:
        """Copia inmutable del mapa, de la dirección 0 al final."""

        return tuple(self._bloques)

    def huecos(self) -> list[Bloque]:
        return [b for b in self._bloques if b.libre]

    def bloque_de(self, proceso_id: str) -> Bloque | None:
        return next((b for b in self._bloques if b.proceso_id == proceso_id), None)

    def tamano_redondeado(self, solicitado_kb: int) -> int:
        """Redondea hacia arriba a la unidad de asignación."""

        unidades = -(-solicitado_kb // self.unidad_kb)  # división techo
        return unidades * self.unidad_kb

    def asignar(self, proceso_id: str, solicitado_kb: int, estrategia: str) -> Bloque:
        """Reserva un bloque contiguo para el proceso y lo devuelve.

        Lanza ``SinEspacioError`` si ningún hueco alcanza y ``ErrorMemoria``
        si el proceso ya tiene memoria asignada.
        """

        if solicitado_kb <= 0:
            raise ValueError("solicitado_kb debe ser mayor que cero")
        if estrategia not in SELECTORES:
            raise ValueError(f"Estrategia desconocida: {estrategia}")
        if self.bloque_de(proceso_id) is not None:
            raise ErrorMemoria(f"{proceso_id} ya tiene un bloque asignado")

        necesario_kb = self.tamano_redondeado(solicitado_kb)
        huecos = self.huecos()
        hueco = SELECTORES[estrategia](huecos, necesario_kb)
        if hueco is None:
            raise SinEspacioError(
                proceso_id,
                necesario_kb,
                libre_total_kb=sum(h.tamano_kb for h in huecos),
                hueco_mayor_kb=max((h.tamano_kb for h in huecos), default=0),
            )

        asignado = Bloque(hueco.inicio_kb, necesario_kb, proceso_id, solicitado_kb)
        sobrante_kb = hueco.tamano_kb - necesario_kb
        partes = [asignado]
        if sobrante_kb:
            partes.append(Bloque(asignado.fin_kb, sobrante_kb))

        posicion = self._bloques.index(hueco)
        self._bloques[posicion:posicion + 1] = partes
        return asignado

    def liberar(self, proceso_id: str) -> Bloque:
        """Libera el bloque del proceso, fusiona huecos vecinos y lo devuelve."""

        bloque = self.bloque_de(proceso_id)
        if bloque is None:
            raise ErrorMemoria(f"{proceso_id} no tiene memoria asignada")

        posicion = self._bloques.index(bloque)
        self._bloques[posicion] = Bloque(bloque.inicio_kb, bloque.tamano_kb)
        self._fusionar_huecos()
        return bloque

    def _fusionar_huecos(self) -> None:
        fusionados: list[Bloque] = []
        for bloque in self._bloques:
            previo = fusionados[-1] if fusionados else None
            if previo is not None and previo.libre and bloque.libre:
                fusionados[-1] = Bloque(previo.inicio_kb, previo.tamano_kb + bloque.tamano_kb)
            else:
                fusionados.append(bloque)
        self._bloques = fusionados
