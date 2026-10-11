"""Métricas de planificación, derivadas de la lista de eventos.

Ningún algoritmo calcula métricas. FCFS, SJF, Prioridad y Round Robin dejan un
registro de eventos y este módulo lo lee. Así las cuatro cifras comparan lo
mismo, medido con la misma regla, y una definición se corrige en un solo lugar.

`calcular_metricas` recibe solo eventos. No toca PCB ni resultados de
algoritmos, y las pruebas lo alimentan con eventos escritos a mano para
comprobarlo.

Definiciones:
  espera       tiempo total en estado LISTO (incluye el que pasa mientras se
               cobra un cambio de contexto)
  retorno      fin - llegada
  respuesta    primer despacho - llegada
  utilización  tiempo ejecutando procesos / tiempo total, en porcentaje
  throughput   procesos terminados por unidad de tiempo
  tiempo total instante del último evento; la corrida arranca en 0
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from core.metricas import exportar_csv, exportar_json, promedio
from core.modelos import Evento, Proceso, SimulationConfig

from .motor import ACCION_CAMBIO_CONTEXTO, ACCION_OCIOSA, ResultadoPlanificacion
from .pcb import ACCION_TRANSICION, EstadoProceso
from .planificador import comparar

NUEVO = EstadoProceso.NUEVO.name
LISTO = EstadoProceso.LISTO.name
EJECUCION = EstadoProceso.EJECUCION.name
TERMINADO = EstadoProceso.TERMINADO.name

COLUMNAS_COMPARACION = (
    "algoritmo",
    "espera_media",
    "retorno_medio",
    "respuesta_media",
    "utilizacion_cpu",
    "throughput",
    "cambios_contexto",
    "tiempo_total",
)

# Para elegir al "mejor" hay que saber en qué dirección mejora cada cifra.
MENOR_ES_MEJOR = frozenset(
    {"espera_media", "retorno_medio", "respuesta_media", "cambios_contexto", "tiempo_total"}
)
MAYOR_ES_MEJOR = frozenset({"utilizacion_cpu", "throughput"})

DECIMALES_EXPORTACION = 4


@dataclass(frozen=True, slots=True)
class MetricasProceso:
    pid: str
    llegada: int
    primer_despacho: int
    fin: int
    rafaga: int  # unidades de CPU que recibió
    espera: int
    retorno: int
    respuesta: int


@dataclass(frozen=True, slots=True)
class MetricasPlanificacion:
    """Todas las cifras de un algoritmo sobre un escenario.

    Las medias, la utilización y el throughput valen None cuando no hubo
    procesos: una media de cero elementos no existe, y mostrar 0 diría algo falso.
    """

    algoritmo: str
    procesos: tuple[MetricasProceso, ...]
    espera_media: float | None
    retorno_medio: float | None
    respuesta_media: float | None
    tiempo_total: int
    tiempo_cpu: int  # ejecutando procesos
    tiempo_ocioso: int  # sin nadie en la cola
    tiempo_cambios: int  # cobrado por cambios de contexto
    utilizacion_cpu: float | None  # porcentaje, 0 a 100
    throughput: float | None
    cambios_contexto: int

    def fila(self) -> dict[str, object]:
        """Una fila con las columnas fijas de la comparación."""
        return {columna: getattr(self, columna) for columna in COLUMNAS_COMPARACION}


def _media(valores: list[int]) -> float | None:
    return promedio(valores) if valores else None


def calcular_metricas(algoritmo: str, eventos: Iterable[Evento]) -> MetricasPlanificacion:
    """Recorre los eventos una vez, en orden, y acumula lo necesario por proceso."""
    llegada: dict[str, int] = {}
    listo_desde: dict[str, int] = {}
    ejecutando_desde: dict[str, int] = {}
    primer_despacho: dict[str, int] = {}
    fin: dict[str, int] = {}
    espera: defaultdict[str, int] = defaultdict(int)
    rafaga: defaultdict[str, int] = defaultdict(int)

    ocioso = 0
    cambios_costo = 0
    cambios = 0
    ultimo_en_cpu: str | None = None
    tiempo_total = 0

    for evento in eventos:
        tiempo_total = max(tiempo_total, evento.instante)

        if evento.accion == ACCION_OCIOSA:
            ocioso += evento.datos["hasta"] - evento.instante
            tiempo_total = max(tiempo_total, evento.datos["hasta"])
            # Tras un hueco, el siguiente proceso no viene a continuación de
            # nadie: no cuenta como cambio de contexto.
            ultimo_en_cpu = None
            continue
        if evento.accion == ACCION_CAMBIO_CONTEXTO:
            cambios_costo += evento.datos["costo"]
            tiempo_total = max(tiempo_total, evento.instante + evento.datos["costo"])
            continue
        if evento.accion != ACCION_TRANSICION:
            continue  # EXPROPIACION y otros eventos informativos repiten una transición

        pid, t = evento.entidad, evento.instante
        desde, hacia = evento.datos["desde"], evento.datos["hacia"]

        if (desde, hacia) == (NUEVO, LISTO):
            llegada[pid] = t
            listo_desde[pid] = t
        elif (desde, hacia) == (LISTO, EJECUCION):
            if pid not in listo_desde:
                raise ValueError(f"{pid}: se despachó sin haber llegado")
            espera[pid] += t - listo_desde[pid]
            primer_despacho.setdefault(pid, t)
            ejecutando_desde[pid] = t
            # Un cambio de contexto es pasar a un proceso distinto del último
            # que corrió. Si el mismo sigue (otro turno), no se cuenta.
            if ultimo_en_cpu is not None and ultimo_en_cpu != pid:
                cambios += 1
            ultimo_en_cpu = pid
        elif desde == EJECUCION and hacia in (LISTO, TERMINADO):
            if pid not in ejecutando_desde:
                raise ValueError(f"{pid}: dejó la CPU sin haber entrado")
            rafaga[pid] += t - ejecutando_desde.pop(pid)
            if hacia == LISTO:
                listo_desde[pid] = t  # expropiado: vuelve a esperar
            else:
                fin[pid] = t

    # Medir un proceso a medias daría retornos y esperas falsos; se rechaza.
    for pid in llegada:
        if pid not in fin:
            raise ValueError(f"{pid}: no terminó, los eventos están incompletos")

    procesos = tuple(
        MetricasProceso(
            pid=pid,
            llegada=llegada[pid],
            primer_despacho=primer_despacho[pid],
            fin=fin[pid],
            rafaga=rafaga[pid],
            espera=espera[pid],
            retorno=fin[pid] - llegada[pid],
            respuesta=primer_despacho[pid] - llegada[pid],
        )
        for pid in sorted(llegada, key=lambda p: (llegada[p], p))
    )
    tiempo_cpu = sum(p.rafaga for p in procesos)
    return MetricasPlanificacion(
        algoritmo=algoritmo,
        procesos=procesos,
        espera_media=_media([p.espera for p in procesos]),
        retorno_medio=_media([p.retorno for p in procesos]),
        respuesta_media=_media([p.respuesta for p in procesos]),
        tiempo_total=tiempo_total,
        tiempo_cpu=tiempo_cpu,
        tiempo_ocioso=ocioso,
        tiempo_cambios=cambios_costo,
        utilizacion_cpu=tiempo_cpu / tiempo_total * 100 if tiempo_total else None,
        throughput=len(procesos) / tiempo_total if tiempo_total else None,
        cambios_contexto=cambios,
    )


def metricas_de(resultado: ResultadoPlanificacion) -> MetricasPlanificacion:
    """Métricas de un resultado. Usa sus eventos y nada más."""
    return calcular_metricas(resultado.algoritmo, resultado.eventos)


@dataclass(frozen=True, slots=True)
class ComparacionAlgoritmos:
    """Las métricas de varios algoritmos sobre el mismo escenario."""

    metricas: tuple[MetricasPlanificacion, ...]

    @classmethod
    def desde_resultados(cls, resultados: Iterable[ResultadoPlanificacion]) -> ComparacionAlgoritmos:
        return cls(tuple(metricas_de(r) for r in resultados))

    @property
    def nombres(self) -> tuple[str, ...]:
        return tuple(m.algoritmo for m in self.metricas)

    def filas(self) -> list[dict[str, object]]:
        return [m.fila() for m in self.metricas]

    def mejor(self, metrica: str) -> str | None:
        """Nombre del algoritmo con la mejor cifra de `metrica`.

        En tiempos y cambios de contexto gana el menor; en utilización y
        throughput, el mayor. Si empatan, gana el que va primero. Devuelve
        None si ningún algoritmo tiene la cifra (escenario vacío).
        """
        if metrica not in MENOR_ES_MEJOR | MAYOR_ES_MEJOR:
            validas = ", ".join(COLUMNAS_COMPARACION[1:])
            raise ValueError(f"métrica desconocida {metrica!r}; válidas: {validas}")
        candidatos = [(m.algoritmo, getattr(m, metrica)) for m in self.metricas]
        candidatos = [(nombre, valor) for nombre, valor in candidatos if valor is not None]
        if not candidatos:
            return None
        elegir = min if metrica in MENOR_ES_MEJOR else max
        mejor_valor = elegir(valor for _, valor in candidatos)
        return next(nombre for nombre, valor in candidatos if valor == mejor_valor)


def comparar_algoritmos(
    procesos: Iterable[Proceso], config: SimulationConfig | None = None
) -> ComparacionAlgoritmos:
    """Corre todos los algoritmos con el mismo escenario y mide cada uno."""
    # `comparar` materializa `procesos` una vez y se lo da igual a cada algoritmo.
    return ComparacionAlgoritmos.desde_resultados(comparar(procesos, config).values())


def _redondear(valor: object) -> object:
    return round(valor, DECIMALES_EXPORTACION) if isinstance(valor, float) else valor


def exportar_comparacion(
    comparacion: ComparacionAlgoritmos, escenario: str | Path, directorio: str | Path = "resultados"
) -> tuple[Path, Path]:
    """Escribe `procesos_<escenario>.csv` y `.json` en `directorio`.

    El CSV lleva una fila por algoritmo, para abrirlo en una hoja de cálculo.
    El JSON agrega el detalle por proceso. El nombre sale del escenario sin
    carpeta ni extensión. Las cifras decimales se redondean a 4 lugares para
    que los archivos sean legibles y estables entre corridas.
    """
    nombre = Path(escenario).stem
    destino = Path(directorio)

    filas = [{k: _redondear(v) for k, v in m.fila().items()} for m in comparacion.metricas]
    ruta_csv = exportar_csv(filas, destino / f"procesos_{nombre}.csv", COLUMNAS_COMPARACION)

    algoritmos = [
        {**fila, "procesos": [asdict(p) for p in m.procesos]}
        for fila, m in zip(filas, comparacion.metricas)
    ]
    ruta_json = exportar_json({"escenario": nombre, "algoritmos": algoritmos}, destino / f"procesos_{nombre}.json")
    return ruta_csv, ruta_json
