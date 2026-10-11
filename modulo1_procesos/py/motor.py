"""Motor común de planificación y tipos de resultado.

Los cuatro algoritmos (FCFS, SJF, Prioridad y Round Robin) comparten casi todo
el trabajo: admitir llegadas, saltar la CPU ociosa, cobrar el cambio de
contexto, registrar eventos y armar el resultado. Eso vive en `Simulacion`,
una sola vez. Cada algoritmo escribe solo su ciclo: a quién elegir y cuánto
tiempo darle.

El motor no imprime nada. Devuelve un `ResultadoPlanificacion` y la capa de
presentación (`diagrama.py`) lo convierte en texto.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from core.metricas import promedio
from core.modelos import Evento, Proceso, SimulationConfig
from core.reloj import RelojLogico

from .pcb import EJECUCION, LISTO, PCB, TERMINADO, TablaProcesos

MODULO = "procesos"
ENTIDAD_CPU = "CPU"
ACCION_OCIOSA = "OCIOSA"
ACCION_EXPROPIACION = "EXPROPIACION"
ACCION_CAMBIO_CONTEXTO = "CAMBIO_CONTEXTO"

# Un criterio recibe el PCB de un proceso listo y devuelve una clave: el
# proceso con la clave menor corre primero. Las claves son tuplas para que el
# desempate quede escrito en el mismo lugar que la regla principal.
Criterio = Callable[[PCB], tuple]


@dataclass(frozen=True, slots=True)
class Segmento:
    """Un tramo de la línea de tiempo de la CPU.

    Con `pid` es ejecución de ese proceso. Sin `pid` es CPU ociosa, o cambio
    de contexto si `cambio_contexto` es True.
    """

    pid: str | None
    inicio: int
    fin: int
    cambio_contexto: bool = False

    def __post_init__(self) -> None:
        if self.inicio < 0 or self.fin <= self.inicio:
            raise ValueError(f"segmento inválido: [{self.inicio}, {self.fin})")
        if self.cambio_contexto and self.pid is not None:
            raise ValueError("un cambio de contexto no pertenece a ningún proceso")


@dataclass(frozen=True, slots=True)
class ResultadoProceso:
    """Tiempos finales de un proceso. Se leen del PCB, no se recalculan aparte."""

    pid: str
    llegada: int
    rafaga: int
    prioridad: int
    inicio: int  # primer despacho
    fin: int
    espera: int  # tiempo fuera de la CPU: retorno - ráfaga
    retorno: int  # fin - llegada
    respuesta: int  # primer despacho - llegada


@dataclass(frozen=True, slots=True)
class ResultadoPlanificacion:
    algoritmo: str
    procesos: tuple[ResultadoProceso, ...]
    segmentos: tuple[Segmento, ...]
    eventos: tuple[Evento, ...]
    cambios_contexto: int = 0

    @property
    def espera_media(self) -> float | None:
        """None si no hubo procesos: una media de cero elementos no existe."""
        return _media([p.espera for p in self.procesos])

    @property
    def retorno_medio(self) -> float | None:
        return _media([p.retorno for p in self.procesos])


def _media(valores: list[int]) -> float | None:
    return promedio(valores) if valores else None


class Simulacion:
    """Estado de una corrida: reloj, cola de listos, eventos y segmentos.

    El algoritmo manda; la simulación ejecuta. Los métodos conservan tres
    garantías que ningún algoritmo debe reimplementar:
      - los eventos salen en orden de tiempo,
      - toda llegada se admite antes de que el proceso en CPU termine o sea
        expropiado, y
      - el cambio de contexto se cobra solo entre dos procesos distintos que
        corren uno tras otro.
    """

    def __init__(
        self, algoritmo: str, procesos: Iterable[Proceso], config: SimulationConfig | None
    ) -> None:
        self.algoritmo = algoritmo
        self.config = config or SimulationConfig()
        self.reloj = RelojLogico()
        self.tabla = TablaProcesos()
        self.listos: list[PCB] = []  # el orden de la lista es el orden de la cola
        self.eventos: list[Evento] = []
        self.segmentos: list[Segmento] = []
        self.cambios_contexto = 0
        self._ultimo_en_cpu: str | None = None

        procesos = list(procesos)
        for proceso in procesos:
            self.tabla.registrar(proceso)  # lanza ValueError si un id se repite
        # Las llegadas se admiten en orden cronológico sin importar cómo vino
        # la lista. Con el mismo (llegada, id) siempre sale la misma corrida.
        self._pendientes = sorted(procesos, key=lambda p: (p.llegada, p.id))
        self._siguiente = 0

    def admitir_hasta(self, limite: int) -> None:
        """Pasa a LISTO a todo proceso que llegó en o antes de `limite`."""
        while self._siguiente < len(self._pendientes) and self._pendientes[self._siguiente].llegada <= limite:
            llegado = self._pendientes[self._siguiente]
            self._siguiente += 1
            # El evento lleva el instante de llegada real, no el del reloj.
            self.eventos.append(self.tabla.transicionar(llegado.id, LISTO, llegado.llegada))
            self.listos.append(self.tabla[llegado.id])

    def esperar_listos(self) -> bool:
        """Deja al menos un proceso listo, o devuelve False si no queda trabajo.

        Si nadie ha llegado, la CPU queda ociosa: el reloj salta a la próxima
        llegada en vez de avanzar unidad por unidad, y el hueco queda
        registrado como segmento y evento.
        """
        while True:
            if self._siguiente >= len(self._pendientes) and not self.listos:
                return False
            self.admitir_hasta(self.reloj.ahora)
            if self.listos:
                return True
            llegada = self._pendientes[self._siguiente].llegada
            self.eventos.append(
                Evento(self.reloj.ahora, MODULO, ENTIDAD_CPU, ACCION_OCIOSA, {"hasta": llegada})
            )
            self.segmentos.append(Segmento(None, self.reloj.ahora, llegada))
            self.reloj.saltar_a(llegada)
            # Tras un hueco, el siguiente proceso no viene "a continuación" de
            # nadie: no hay cambio de contexto que contar ni cobrar.
            self._ultimo_en_cpu = None

    def despachar(self, pcb: PCB) -> None:
        """Pone a `pcb` en la CPU. Si hay cambio de contexto, lo cuenta y lo cobra."""
        if self._ultimo_en_cpu is not None and self._ultimo_en_cpu != pcb.pid:
            self.cambios_contexto += 1
            costo = self.config.cambio_contexto
            if costo > 0:
                self._cobrar_cambio(self._ultimo_en_cpu, pcb.pid, costo)
        self.eventos.append(self.tabla.transicionar(pcb.pid, EJECUCION, self.reloj.ahora))
        self._ultimo_en_cpu = pcb.pid

    def _cobrar_cambio(self, saliente: str, entrante: str, costo: int) -> None:
        inicio = self.reloj.ahora
        fin = inicio + costo
        self.eventos.append(
            Evento(inicio, MODULO, ENTIDAD_CPU, ACCION_CAMBIO_CONTEXTO, {"de": saliente, "a": entrante, "costo": costo})
        )
        # Quién corre ya está decidido; llegar durante el cambio no lo altera,
        # pero esos procesos entran a la cola antes de que el reloj avance.
        self.admitir_hasta(fin)
        self.segmentos.append(Segmento(None, inicio, fin, cambio_contexto=True))
        self.reloj.saltar_a(fin)

    def correr(self, pcb: PCB, unidades: int) -> None:
        """Da `unidades` de CPU a `pcb` y avanza el reloj."""
        inicio = self.reloj.ahora
        fin = inicio + unidades
        pcb.ejecutar(unidades)
        # Los que llegan mientras `pcb` corre entran a la cola antes de que
        # termine o vuelva a ella. Con eso, un proceso que llega justo al
        # agotarse el quantum queda delante del expropiado.
        self.admitir_hasta(fin)
        self.reloj.saltar_a(fin)
        self.segmentos.append(Segmento(pcb.pid, inicio, fin))

    def terminar(self, pcb: PCB) -> None:
        self.eventos.append(self.tabla.transicionar(pcb.pid, TERMINADO, self.reloj.ahora))

    def expropiar(self, pcb: PCB) -> None:
        """Devuelve `pcb` al final de la cola y deja constancia del estado de la cola."""
        instante = self.reloj.ahora
        self.eventos.append(self.tabla.transicionar(pcb.pid, LISTO, instante))
        self.listos.append(pcb)
        self.eventos.append(
            Evento(
                instante,
                MODULO,
                pcb.pid,
                ACCION_EXPROPIACION,
                {"restante": pcb.rafaga_restante, "cola": tuple(p.pid for p in self.listos)},
            )
        )

    def resultado(self) -> ResultadoPlanificacion:
        procesos = tuple(
            ResultadoProceso(
                pid=p.pid,
                llegada=p.llegada,
                rafaga=p.rafaga_total,
                prioridad=p.prioridad,
                inicio=p.t_primera_cpu,
                fin=p.t_fin,
                espera=p.t_fin - p.llegada - p.rafaga_total,
                retorno=p.t_fin - p.llegada,
                respuesta=p.t_primera_cpu - p.llegada,
            )
            for p in sorted(self.tabla, key=lambda p: (p.llegada, p.pid))
        )
        return ResultadoPlanificacion(
            self.algoritmo, procesos, tuple(self.segmentos), tuple(self.eventos), self.cambios_contexto
        )


def planificar_no_expropiativo(
    algoritmo: str,
    procesos: Iterable[Proceso],
    config: SimulationConfig | None,
    criterio: Criterio,
) -> ResultadoPlanificacion:
    """Ciclo de FCFS, SJF y Prioridad: elegir por criterio y correr hasta el final."""
    simulacion = Simulacion(algoritmo, procesos, config)
    while simulacion.esperar_listos():
        elegido = min(simulacion.listos, key=criterio)
        simulacion.listos.remove(elegido)
        simulacion.despachar(elegido)
        simulacion.correr(elegido, elegido.rafaga_total)  # sin expropiación: corre completo
        simulacion.terminar(elegido)
    return simulacion.resultado()
