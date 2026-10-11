"""Modelos compartidos de SO-Sim: proceso, evento, configuración y resultado.

Todos los módulos hablan este idioma. Los datos son inmutables y se validan al
construirse, así que un objeto que existe ya es válido y ningún algoritmo
revisa sus entradas de nuevo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

# Los textos de estado coinciden con los que el Módulo 4 ya publica.
COMPLETADO = "completado"
COMPLETADO_CON_ERRORES = "completado_con_errores"
FALLIDO = "fallido"
ESTADOS = (COMPLETADO, COMPLETADO_CON_ERRORES, FALLIDO)


def _exigir_entero(nombre: str, valor: object, minimo: int) -> None:
    # bool hereda de int en Python; True no cuenta como entero válido aquí.
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ValueError(f"{nombre} debe ser un entero, recibió {valor!r}")
    if valor < minimo:
        raise ValueError(f"{nombre} debe ser >= {minimo}, recibió {valor}")


def _exigir_texto(nombre: str, valor: object) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre} no puede estar vacío")


@dataclass(frozen=True, slots=True)
class Proceso:
    """Una fila de lote_*.csv: lo que el planificador sabe de un proceso."""

    id: str
    llegada: int
    rafaga: int
    prioridad: int
    memoria_kb: int
    cursos: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _exigir_texto("id", self.id)
        _exigir_entero("llegada", self.llegada, 0)
        # Una ráfaga de 0 nunca ocuparía la CPU; el planificador no la aceptaría.
        _exigir_entero("rafaga", self.rafaga, 1)
        _exigir_entero("prioridad", self.prioridad, 0)
        _exigir_entero("memoria_kb", self.memoria_kb, 1)
        # El dataclass es frozen: se usa object.__setattr__ solo para normalizar
        # la lista que llega del cargador a una tupla inmutable.
        object.__setattr__(self, "cursos", tuple(self.cursos))


@dataclass(frozen=True, slots=True)
class Evento:
    """Un hecho de la simulación con su instante lógico.

    Los campos replican el Evento del Módulo 4, así que migrarlo cuesta un
    cambio de import.
    """

    instante: int
    modulo: str
    entidad: str
    accion: str
    datos: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _exigir_entero("instante", self.instante, 0)
        _exigir_texto("modulo", self.modulo)
        _exigir_texto("entidad", self.entidad)
        _exigir_texto("accion", self.accion)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Parámetros de una corrida. El orquestador la crea y cada módulo la lee."""

    escenario: Path | None = None
    algoritmo: str = "todos"
    quantum: int = 2
    cambio_contexto: int = 0
    directorio_resultados: Path = Path("resultados")

    def __post_init__(self) -> None:
        # La CLI entrega rutas como texto; aquí se unifican a Path.
        if self.escenario is not None:
            object.__setattr__(self, "escenario", Path(self.escenario))
        object.__setattr__(self, "directorio_resultados", Path(self.directorio_resultados))
        _exigir_texto("algoritmo", self.algoritmo)
        _exigir_entero("quantum", self.quantum, 1)
        _exigir_entero("cambio_contexto", self.cambio_contexto, 0)


@dataclass(frozen=True, slots=True)
class ModuleResult:
    """Lo único que un módulo devuelve al orquestador.

    Los módulos no imprimen para comunicarse: la CLI lee estos campos y las
    pruebas los inspeccionan.
    """

    modulo: str
    estado: str
    eventos: tuple[Evento, ...] = ()
    metricas: Mapping[str, object] = field(default_factory=dict)
    errores: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _exigir_texto("modulo", self.modulo)
        object.__setattr__(self, "eventos", tuple(self.eventos))
        object.__setattr__(self, "errores", tuple(self.errores))
        if self.estado not in ESTADOS:
            raise ValueError(f"estado desconocido: {self.estado!r}")
        # El estado y la lista de errores deben decir lo mismo. Si no, un fallo
        # pasaría por éxito sin que nadie lo vea.
        if self.estado == COMPLETADO and self.errores:
            raise ValueError("un resultado 'completado' no puede traer errores")
        if self.estado != COMPLETADO and not self.errores:
            raise ValueError(f"un resultado '{self.estado}' necesita al menos un error")


__all__ = (
    "COMPLETADO",
    "COMPLETADO_CON_ERRORES",
    "ESTADOS",
    "FALLIDO",
    "Evento",
    "ModuleResult",
    "Proceso",
    "SimulationConfig",
)
