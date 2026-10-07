"""Calcula fragmentación interna y externa a partir del mapa de bloques.

Las funciones solo leen una lista de ``Bloque``; no modifican la memoria.
Así se pueden medir el estado después de cada paso o al final.

Fragmentación interna
    Memoria entregada a un proceso que este no pidió. Aparece por redondear
    a la unidad de asignación: pedir 96 KB con unidad de 64 KB entrega
    128 KB, y esos 32 KB quedan desperdiciados *dentro* del bloque.

    porcentaje = desperdicio total / memoria asignada total × 100

Fragmentación externa
    Memoria libre repartida en huecos separados. El total libre puede
    alcanzar para un proceso, pero ningún hueco por sí solo es suficiente.

    porcentaje = (1 - hueco mayor / memoria libre total) × 100

    0 % significa que toda la memoria libre es un único hueco; cerca de
    100 % significa que está muy repartida en huecos pequeños.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .asignacion_contigua import Bloque


@dataclass(frozen=True, slots=True)
class FragmentacionInterna:
    asignado_kb: int
    solicitado_kb: int
    desperdicio_kb: int
    porcentaje: float


@dataclass(frozen=True, slots=True)
class FragmentacionExterna:
    libre_total_kb: int
    hueco_mayor_kb: int
    cantidad_huecos: int
    porcentaje: float


@dataclass(frozen=True, slots=True)
class ReporteFragmentacion:
    interna: FragmentacionInterna
    externa: FragmentacionExterna

    def como_diccionario(self) -> dict[str, float | int]:
        """Métricas planas, listas para un CSV o para el resultado del módulo."""

        return {
            "asignado_kb": self.interna.asignado_kb,
            "solicitado_kb": self.interna.solicitado_kb,
            "fragmentacion_interna_kb": self.interna.desperdicio_kb,
            "fragmentacion_interna_pct": self.interna.porcentaje,
            "libre_total_kb": self.externa.libre_total_kb,
            "hueco_mayor_kb": self.externa.hueco_mayor_kb,
            "cantidad_huecos": self.externa.cantidad_huecos,
            "fragmentacion_externa_pct": self.externa.porcentaje,
        }


def _porcentaje(parte: int, total: int) -> float:
    return round(parte / total * 100, 2) if total else 0.0


def fragmentacion_interna(bloques: Iterable[Bloque]) -> FragmentacionInterna:
    ocupados = [b for b in bloques if not b.libre]
    asignado = sum(b.tamano_kb for b in ocupados)
    solicitado = sum(b.solicitado_kb for b in ocupados)
    desperdicio = asignado - solicitado
    return FragmentacionInterna(asignado, solicitado, desperdicio,
                                _porcentaje(desperdicio, asignado))


def fragmentacion_externa(bloques: Iterable[Bloque]) -> FragmentacionExterna:
    huecos = [b.tamano_kb for b in bloques if b.libre]
    libre_total = sum(huecos)
    hueco_mayor = max(huecos, default=0)
    return FragmentacionExterna(
        libre_total,
        hueco_mayor,
        len(huecos),
        _porcentaje(libre_total - hueco_mayor, libre_total),
    )


def medir(bloques: Iterable[Bloque]) -> ReporteFragmentacion:
    """Mide ambas fragmentaciones sobre el mismo mapa."""

    mapa = list(bloques)
    return ReporteFragmentacion(fragmentacion_interna(mapa), fragmentacion_externa(mapa))
