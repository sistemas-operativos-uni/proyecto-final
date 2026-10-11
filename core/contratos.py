"""Interfaz estable entre el orquestador y los módulos del simulador."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .modelos import ModuleResult, SimulationConfig


@runtime_checkable
class ModuloSimulacion(Protocol):
    """Todo módulo de SO-Sim expone un nombre y una operación `ejecutar`.

    Es un Protocol, no una clase base: los módulos no importan ni heredan de
    nada en core, y el orquestador los trata por su forma. Así un módulo
    nuevo se enchufa sin tocar el núcleo.
    """

    nombre: str

    def ejecutar(self, config: SimulationConfig) -> ModuleResult:
        """Corre la simulación con `config` y devuelve el resultado completo."""
        ...
