"""Round Robin: cola FIFO y un quantum de CPU por turno.

Cada proceso corre como máximo `config.quantum` unidades. Si no terminó, vuelve
al final de la cola y el siguiente toma la CPU. Reparte el tiempo con justicia
y da buena respuesta, a cambio de más cambios de contexto que FCFS.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.modelos import Proceso, SimulationConfig

from .motor import ResultadoPlanificacion, Simulacion

NOMBRE = "RR"


def planificar(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> ResultadoPlanificacion:
    config = config or SimulationConfig()
    # El quantum ya viene validado (> 0) por SimulationConfig. El nombre lo
    # lleva incluido para que el log y la tabla distingan RR(q=2) de RR(q=5).
    simulacion = Simulacion(f"{NOMBRE}(q={config.quantum})", procesos, config)

    while simulacion.esperar_listos():
        # Cola FIFO: sale el que lleva más tiempo esperando. No hay criterio
        # de elección, por eso este algoritmo no usa `planificar_no_expropiativo`.
        pcb = simulacion.listos.pop(0)
        simulacion.despachar(pcb)
        simulacion.correr(pcb, min(config.quantum, pcb.rafaga_restante))

        if pcb.rafaga_restante == 0:
            simulacion.terminar(pcb)
        else:
            # `correr` ya admitió a los que llegaron durante el turno, incluidos
            # los que llegaron justo al expirar: entran a la cola antes que `pcb`.
            simulacion.expropiar(pcb)

    return simulacion.resultado()
