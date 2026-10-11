"""Bloque de control de proceso (PCB), sus estados y la tabla de procesos.

Aquí vive la única definición del ciclo de vida de un proceso. FCFS, SJF,
Prioridad y Round Robin cambian estados a través de estas clases y no
mantienen estado propio, así que una regla se escribe y se prueba una vez.

Diagrama de estados (una flecha es una transición permitida)::

    NUEVO -> LISTO -> EJECUCION -> TERMINADO
               ^         |  |
               |         |  +--> BLOQUEADO
               +---------+          |
               +----------------------+

Los instantes los decide el llamador (el reloj lógico de `core`); el PCB solo
verifica que no retrocedan.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from types import MappingProxyType

from core.modelos import Evento, Proceso

MODULO = "procesos"
ACCION_TRANSICION = "TRANSICION"


class EstadoProceso(Enum):
    NUEVO = "NUEVO"
    LISTO = "LISTO"
    EJECUCION = "EJECUCION"
    BLOQUEADO = "BLOQUEADO"
    TERMINADO = "TERMINADO"


NUEVO = EstadoProceso.NUEVO
LISTO = EstadoProceso.LISTO
EJECUCION = EstadoProceso.EJECUCION
BLOQUEADO = EstadoProceso.BLOQUEADO
TERMINADO = EstadoProceso.TERMINADO

# Fuente única de verdad de las transiciones. Es de solo lectura para que
# ningún algoritmo agregue un atajo (por ejemplo LISTO -> TERMINADO).
# EJECUCION -> LISTO es la expropiación de Round Robin; BLOQUEADO -> LISTO
# es el fin de una espera de E/S.
TRANSICIONES = MappingProxyType(
    {
        NUEVO: frozenset({LISTO}),
        LISTO: frozenset({EJECUCION}),
        EJECUCION: frozenset({LISTO, BLOQUEADO, TERMINADO}),
        BLOQUEADO: frozenset({LISTO}),
        TERMINADO: frozenset(),
    }
)


class TransicionInvalida(ValueError):
    """El cambio de estado o la operación rompe una regla del ciclo de vida."""


def _es_entero(valor: object) -> bool:
    # `type(...) is int` deja fuera a bool, que en Python también es int.
    return type(valor) is int


class PCB:
    """Estado de un proceso durante la simulación.

    Los campos se leen por propiedades de solo lectura. Solo `transicionar` y
    `ejecutar` los modifican, y ambos validan antes de escribir: si lanzan,
    el PCB queda exactamente como estaba.
    """

    __slots__ = (
        "_pid",
        "_prioridad",
        "_llegada",
        "_rafaga_total",
        "_rafaga_restante",
        "_estado",
        "_ultimo_cambio",
        "_t_primera_cpu",
        "_t_fin",
    )

    def __init__(self, pid: str, llegada: int, rafaga: int, prioridad: int) -> None:
        self._pid = pid
        self._prioridad = prioridad
        self._llegada = llegada
        self._rafaga_total = rafaga
        self._rafaga_restante = rafaga
        self._estado = NUEVO
        # Parte de la llegada: el proceso no puede existir antes de ella.
        self._ultimo_cambio = llegada
        self._t_primera_cpu: int | None = None
        self._t_fin: int | None = None

    @classmethod
    def desde_proceso(cls, proceso: Proceso) -> PCB:
        return cls(proceso.id, proceso.llegada, proceso.rafaga, proceso.prioridad)

    @property
    def pid(self) -> str:
        return self._pid

    @property
    def estado(self) -> EstadoProceso:
        return self._estado

    @property
    def prioridad(self) -> int:
        return self._prioridad

    @property
    def llegada(self) -> int:
        return self._llegada

    @property
    def rafaga_total(self) -> int:
        return self._rafaga_total

    @property
    def rafaga_restante(self) -> int:
        return self._rafaga_restante

    @property
    def ultimo_cambio(self) -> int:
        return self._ultimo_cambio

    @property
    def t_primera_cpu(self) -> int | None:
        """Instante del primer despacho. Base del tiempo de respuesta."""
        return self._t_primera_cpu

    @property
    def t_fin(self) -> int | None:
        return self._t_fin

    def transicionar(self, nuevo: EstadoProceso, instante: int) -> None:
        """Pasa al estado `nuevo` en `instante`, o lanza sin tocar nada."""
        if not _es_entero(instante) or instante < 0:
            raise ValueError(f"{self._pid}: instante debe ser un entero >= 0, recibió {instante!r}")

        if nuevo not in TRANSICIONES[self._estado]:
            raise TransicionInvalida(
                f"{self._pid}: transición {self._estado.name} -> {nuevo.name} no permitida"
            )

        # Invariante de ráfaga: la CPU solo libera a un proceso terminado
        # cuando consumió toda su ráfaga, y un proceso sin ráfaga pendiente
        # no tiene otro destino que TERMINADO.
        if self._estado is EJECUCION:
            if nuevo is TERMINADO and self._rafaga_restante != 0:
                raise TransicionInvalida(
                    f"{self._pid}: no puede terminar con ráfaga restante {self._rafaga_restante}"
                )
            if nuevo is not TERMINADO and self._rafaga_restante == 0:
                raise TransicionInvalida(
                    f"{self._pid}: con ráfaga agotada solo puede pasar a TERMINADO, no a {nuevo.name}"
                )

        if instante < self._ultimo_cambio:
            raise ValueError(
                f"{self._pid}: el tiempo no puede retroceder ({instante} < {self._ultimo_cambio})"
            )

        # Todas las comprobaciones pasaron: desde aquí se escribe.
        self._estado = nuevo
        self._ultimo_cambio = instante
        if nuevo is EJECUCION and self._t_primera_cpu is None:
            self._t_primera_cpu = instante
        elif nuevo is TERMINADO:
            self._t_fin = instante

    def ejecutar(self, unidades: int) -> None:
        """Consume `unidades` de ráfaga. Solo vale con el proceso en CPU."""
        if self._estado is not EJECUCION:
            raise TransicionInvalida(
                f"{self._pid}: solo ejecuta en EJECUCION, está en {self._estado.name}"
            )
        if not _es_entero(unidades) or unidades < 1:
            raise ValueError(f"{self._pid}: unidades debe ser un entero >= 1, recibió {unidades!r}")
        # Pasar de largo dejaría la ráfaga restante en negativo.
        if unidades > self._rafaga_restante:
            raise ValueError(
                f"{self._pid}: pide {unidades} unidades y quedan {self._rafaga_restante}"
            )
        self._rafaga_restante -= unidades

    def __repr__(self) -> str:
        return (
            f"PCB({self._pid}, {self._estado.name}, "
            f"restante={self._rafaga_restante}/{self._rafaga_total})"
        )


class TablaProcesos:
    """Todos los PCB de una simulación y el registro de sus transiciones.

    Es el punto por donde pasan los cambios de estado de los algoritmos.
    Añade dos reglas que un PCB aislado no puede ver: hay una sola CPU y el
    tiempo global no retrocede entre procesos.
    """

    def __init__(self) -> None:
        self._pcbs: dict[str, PCB] = {}
        self._eventos: list[Evento] = []
        self._ultimo_instante = 0

    def registrar(self, proceso: Proceso) -> PCB:
        if proceso.id in self._pcbs:
            raise ValueError(f"el proceso {proceso.id} ya está registrado")
        pcb = PCB.desde_proceso(proceso)
        self._pcbs[proceso.id] = pcb
        return pcb

    def __getitem__(self, pid: str) -> PCB:
        return self._pcbs[pid]

    def __len__(self) -> int:
        return len(self._pcbs)

    def __iter__(self) -> Iterator[PCB]:
        return iter(self._pcbs.values())

    @property
    def eventos(self) -> tuple[Evento, ...]:
        return tuple(self._eventos)

    @property
    def en_ejecucion(self) -> PCB | None:
        # Se deriva de los PCB en vez de guardarse aparte: así no existe una
        # segunda copia que pueda quedar desfasada.
        return next((p for p in self._pcbs.values() if p.estado is EJECUCION), None)

    def transicionar(self, pid: str, nuevo: EstadoProceso, instante: int) -> Evento:
        pcb = self._pcbs[pid]

        # Regla de CPU única. Se revisa antes de mutar: un despacho rechazado
        # no deja rastro ni en el PCB ni en los eventos.
        ocupante = self.en_ejecucion
        if nuevo is EJECUCION and ocupante is not None and ocupante is not pcb:
            raise TransicionInvalida(
                f"{pid}: la CPU está ocupada por {ocupante.pid}, no puede pasar a EJECUCION"
            )
        if _es_entero(instante) and instante < self._ultimo_instante:
            raise ValueError(
                f"{pid}: el tiempo no puede retroceder ({instante} < {self._ultimo_instante})"
            )

        origen = pcb.estado
        pcb.transicionar(nuevo, instante)  # valida las reglas propias del PCB

        self._ultimo_instante = instante
        evento = Evento(
            instante=instante,
            modulo=MODULO,
            entidad=pid,
            accion=ACCION_TRANSICION,
            datos={"desde": origen.name, "hacia": nuevo.name, "restante": pcb.rafaga_restante},
        )
        self._eventos.append(evento)
        return evento
