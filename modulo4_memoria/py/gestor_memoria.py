"""Mantiene el mapa de bloques contiguos y coordina solicitudes de procesos.

El gestor es la cara pública del Módulo 4. Recibe una secuencia de
solicitudes (``asignar`` o ``liberar``), las aplica sobre una
``MemoriaContigua`` con la estrategia elegida y, después de cada paso, mide
la fragmentación. Devuelve un ``ResultadoMemoria`` con estado, eventos,
métricas y errores recuperables, como pide ``docs/arquitectura.md``.

Un error de una solicitud (sin espacio, proceso desconocido, tamaño que no
coincide) no detiene la simulación: queda registrado y se sigue con el paso
siguiente.

Pendiente de integración: ``core/modelos.py`` y ``core/contratos.py`` todavía
no definen ``SimulationConfig`` ni ``ModuleResult``. Mientras tanto este
módulo usa sus propias clases con los mismos campos acordados; cuando el
núcleo exista, ``ResultadoMemoria`` se adapta a ``ModuleResult``.

Uso desde la raíz del repositorio::

    python -m modulo4_memoria.py.gestor_memoria
    python -m modulo4_memoria.py.gestor_memoria --estrategia mejor --total 512 --unidad 64
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .asignacion_contigua import (
    ESTRATEGIAS,
    Bloque,
    ErrorMemoria,
    MemoriaContigua,
    SinEspacioError,
)
from .fragmentacion import medir

MODULO = "memoria"
ASIGNAR = "asignar"
LIBERAR = "liberar"
OPERACIONES = (ASIGNAR, LIBERAR)

# Valores provisionales hasta que core/ defina la configuración común.
# 512 KB cubren el pico del escenario (384 KB) y la unidad de 64 KB
# hace visible la fragmentación interna (96 KB ocupan 128 KB).
MEMORIA_TOTAL_KB = 512
UNIDAD_ASIGNACION_KB = 64
ESCENARIO_POR_DEFECTO = Path("escenarios/solicitudes_memoria.csv")


@dataclass(frozen=True, slots=True)
class Solicitud:
    paso: int
    proceso_id: str
    operacion: str
    tamano_kb: int


@dataclass(frozen=True, slots=True)
class Evento:
    """Registro de un paso: instante lógico, módulo, entidad, acción y datos."""

    instante: int
    modulo: str
    entidad: str
    accion: str
    datos: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResultadoMemoria:
    estrategia: str
    estado: str  # "completado" o "completado_con_errores"
    eventos: tuple[Evento, ...]
    metricas: dict[str, object]
    errores: tuple[str, ...]
    mapa_final: tuple[Bloque, ...]


def cargar_solicitudes(ruta: str | Path) -> list[Solicitud]:
    """Lee y valida el CSV ``paso,proceso_id,operacion,tamano_kb``."""

    solicitudes: list[Solicitud] = []
    with open(ruta, newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        esperadas = {"paso", "proceso_id", "operacion", "tamano_kb"}
        if not esperadas.issubset(lector.fieldnames or ()):
            raise ValueError(f"El escenario debe tener las columnas {sorted(esperadas)}")
        for numero, fila in enumerate(lector, start=2):
            operacion = fila["operacion"].strip()
            if operacion not in OPERACIONES:
                raise ValueError(f"Línea {numero}: operación desconocida '{operacion}'")
            tamano = int(fila["tamano_kb"])
            if tamano <= 0:
                raise ValueError(f"Línea {numero}: tamano_kb debe ser mayor que cero")
            solicitudes.append(
                Solicitud(int(fila["paso"]), fila["proceso_id"].strip(), operacion, tamano)
            )
    return solicitudes


class GestorMemoria:
    """Aplica solicitudes sobre la memoria con una estrategia fija."""

    def __init__(self, total_kb: int = MEMORIA_TOTAL_KB,
                 unidad_kb: int = UNIDAD_ASIGNACION_KB,
                 estrategia: str = "primer") -> None:
        if estrategia not in ESTRATEGIAS:
            raise ValueError(f"Estrategia desconocida: {estrategia}")
        self.estrategia = estrategia
        self.memoria = MemoriaContigua(total_kb, unidad_kb)

    def procesar(self, solicitud: Solicitud) -> Evento:
        """Aplica una solicitud; los errores recuperables vuelven como evento."""

        datos: dict[str, object] = {"tamano_kb": solicitud.tamano_kb}
        try:
            if solicitud.operacion == ASIGNAR:
                bloque = self.memoria.asignar(
                    solicitud.proceso_id, solicitud.tamano_kb, self.estrategia
                )
                accion = "asignado"
            else:
                bloque = self._liberar(solicitud)
                accion = "liberado"
            datos.update(inicio_kb=bloque.inicio_kb, fin_kb=bloque.fin_kb,
                         asignado_kb=bloque.tamano_kb)
        except SinEspacioError as error:
            accion = "rechazado"
            datos.update(error=str(error), por_fragmentacion=error.por_fragmentacion)
        except ErrorMemoria as error:
            accion = "error"
            datos.update(error=str(error))

        datos["mapa"] = self.mapa_texto()
        datos["fragmentacion"] = medir(self.memoria.bloques).como_diccionario()
        return Evento(solicitud.paso, MODULO, solicitud.proceso_id, accion, datos)

    def _liberar(self, solicitud: Solicitud) -> Bloque:
        bloque = self.memoria.bloque_de(solicitud.proceso_id)
        if bloque is not None and bloque.solicitado_kb != solicitud.tamano_kb:
            raise ErrorMemoria(
                f"{solicitud.proceso_id} pidió {bloque.solicitado_kb} KB, "
                f"no {solicitud.tamano_kb} KB; no se libera"
            )
        return self.memoria.liberar(solicitud.proceso_id)

    def mapa_texto(self) -> str:
        """Mapa legible, de la dirección 0 al final: ``[P001 128|libre 64|...]``."""

        partes = [
            f"{'libre' if b.libre else b.proceso_id} {b.tamano_kb}"
            for b in self.memoria.bloques
        ]
        return "[" + " | ".join(partes) + "]"

    def ejecutar(self, solicitudes: Iterable[Solicitud]) -> ResultadoMemoria:
        """Procesa todas las solicitudes en orden y resume el resultado."""

        eventos = tuple(self.procesar(s) for s in sorted(solicitudes, key=lambda s: s.paso))
        errores = tuple(str(e.datos["error"]) for e in eventos if "error" in e.datos)
        final = medir(self.memoria.bloques).como_diccionario()
        externa_por_paso = [e.datos["fragmentacion"]["fragmentacion_externa_pct"]
                            for e in eventos]
        interna_por_paso = [e.datos["fragmentacion"]["fragmentacion_interna_kb"]
                            for e in eventos]

        metricas: dict[str, object] = {
            "estrategia": self.estrategia,
            "memoria_total_kb": self.memoria.total_kb,
            "unidad_kb": self.memoria.unidad_kb,
            "pasos": len(eventos),
            "asignaciones": sum(e.accion == "asignado" for e in eventos),
            "liberaciones": sum(e.accion == "liberado" for e in eventos),
            "rechazos": sum(e.accion == "rechazado" for e in eventos),
            "rechazos_por_fragmentacion": sum(
                bool(e.datos.get("por_fragmentacion")) for e in eventos
            ),
            "max_fragmentacion_externa_pct": max(externa_por_paso, default=0.0),
            "max_fragmentacion_interna_kb": max(interna_por_paso, default=0),
            **{f"final_{clave}": valor for clave, valor in final.items()},
        }
        estado = "completado_con_errores" if errores else "completado"
        return ResultadoMemoria(self.estrategia, estado, eventos, metricas, errores,
                                self.memoria.bloques)


def comparar_estrategias(solicitudes: Sequence[Solicitud],
                         total_kb: int = MEMORIA_TOTAL_KB,
                         unidad_kb: int = UNIDAD_ASIGNACION_KB,
                         ) -> dict[str, ResultadoMemoria]:
    """Ejecuta las tres estrategias sobre exactamente el mismo escenario."""

    return {
        estrategia: GestorMemoria(total_kb, unidad_kb, estrategia).ejecutar(solicitudes)
        for estrategia in ESTRATEGIAS
    }


def _imprimir(resultado: ResultadoMemoria) -> None:
    print(f"\n=== Estrategia: {resultado.estrategia} ajuste ({resultado.estado}) ===")
    for evento in resultado.eventos:
        frag = evento.datos["fragmentacion"]
        print(
            f"paso {evento.instante}: {evento.entidad} {evento.accion:<9} "
            f"{evento.datos['mapa']}  "
            f"interna={frag['fragmentacion_interna_kb']} KB  "
            f"externa={frag['fragmentacion_externa_pct']}%"
        )
        if "error" in evento.datos:
            print(f"        -> {evento.datos['error']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Módulo 4: memoria contigua")
    parser.add_argument("--escenario", type=Path, default=ESCENARIO_POR_DEFECTO)
    parser.add_argument("--estrategia", choices=(*ESTRATEGIAS, "todas"), default="todas")
    parser.add_argument("--total", type=int, default=MEMORIA_TOTAL_KB)
    parser.add_argument("--unidad", type=int, default=UNIDAD_ASIGNACION_KB)
    args = parser.parse_args(argv)

    solicitudes = cargar_solicitudes(args.escenario)
    if args.estrategia == "todas":
        resultados = comparar_estrategias(solicitudes, args.total, args.unidad)
    else:
        gestor = GestorMemoria(args.total, args.unidad, args.estrategia)
        resultados = {args.estrategia: gestor.ejecutar(solicitudes)}

    for resultado in resultados.values():
        _imprimir(resultado)

    print("\nResumen")
    for nombre, resultado in resultados.items():
        m = resultado.metricas
        print(
            f"{nombre:>6}: rechazos={m['rechazos']} "
            f"max_externa={m['max_fragmentacion_externa_pct']}% "
            f"max_interna={m['max_fragmentacion_interna_kb']} KB"
        )
    return 0 if all(r.estado == "completado" for r in resultados.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
