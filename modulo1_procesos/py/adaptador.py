"""Adaptador del Módulo 1 al contrato común de SO-Sim.

`ModuloProcesos` implementa `ModuloSimulacion`: el orquestador le pasa un
`SimulationConfig` y recibe un `ModuleResult` con estado, eventos, métricas y
errores. Es la única puerta de entrada del módulo para el resto del sistema.

Regla de errores: ningún problema del escenario escapa como excepción ni se
pierde. Queda en `ModuleResult.errores` y el estado lo refleja:

  completado              todo salió bien
  completado_con_errores  se simuló, pero una fila del escenario o la
                          exportación falló (el error es recuperable)
  fallido                 no había nada que simular

El adaptador no imprime. La presentación pertenece a la CLI.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from core.cargador_escenarios import ErrorEscenario, cargar_procesos_tolerante
from core.modelos import (
    COMPLETADO,
    COMPLETADO_CON_ERRORES,
    FALLIDO,
    Evento,
    ModuleResult,
    SimulationConfig,
)

from .graficos import graficar_comparacion
from .metricas_planificacion import ComparacionAlgoritmos, exportar_comparacion
from .motor import MODULO, ResultadoPlanificacion
from .planificador import ALGORITMOS, comparar, planificar, validos

NOMBRE = MODULO
TODOS = "TODOS"
ESCENARIO_POR_DEFECTO = Path(__file__).resolve().parents[2] / "escenarios" / "lote_pequeno.csv"


def _fallido(escenario: str, errores: list[str]) -> ModuleResult:
    # Sin simulación no hay eventos ni métricas; solo se conserva qué escenario
    # se intentó, para que el mensaje de error tenga contexto.
    return ModuleResult(NOMBRE, FALLIDO, (), {"escenario": escenario}, tuple(errores))


def _etiquetar(resultado: ResultadoPlanificacion) -> list[Evento]:
    """Copia los eventos de un algoritmo marcando cuál los produjo.

    El `Evento` no trae el algoritmo y, al juntar varios en un mismo
    resultado, sin esa marca no se sabría de qué simulación es cada uno.
    """
    return [
        dataclasses.replace(evento, datos={**evento.datos, "algoritmo": resultado.algoritmo})
        for evento in resultado.eventos
    ]


class ModuloProcesos:
    """Procesos, hilos y planificación (Módulo 1) como módulo de SO-Sim."""

    nombre = NOMBRE

    def ejecutar(self, config: SimulationConfig) -> ModuleResult:
        escenario = config.escenario or ESCENARIO_POR_DEFECTO
        elegido = config.algoritmo.strip().upper()

        # Las dos comprobaciones de configuración van primero: fallar aquí
        # evita leer el escenario o escribir archivos para nada.
        if elegido != TODOS and elegido not in ALGORITMOS:
            return _fallido(escenario.name, [f"algoritmo desconocido {config.algoritmo!r}; válidos: {validos()}"])
        if config.exportar and elegido != TODOS:
            # Lo que se exporta es una comparación; con un solo algoritmo
            # no hay nada que comparar y el archivo saldría engañoso.
            return _fallido(escenario.name, ["exportar compara algoritmos: use el algoritmo 'todos'"])

        # Un problema de archivo (no existe, cabecera inválida) no deja ni una
        # fila utilizable. Una fila mala, en cambio, se anota y se sigue.
        try:
            carga = cargar_procesos_tolerante(escenario)
        except ErrorEscenario as error:
            return _fallido(escenario.name, [str(error)])

        errores = list(carga.errores)
        if not carga.procesos:
            errores.append(
                "no queda ningún proceso válido para simular" if errores else "el escenario no tiene procesos"
            )
            return _fallido(escenario.name, errores)

        if elegido == TODOS:
            resultados = list(comparar(carga.procesos, config).values())
        else:
            resultados = [planificar(elegido, carga.procesos, config)]

        # Cada algoritmo es una simulación con su propio reloj: sus eventos se
        # concatenan por algoritmo, en el orden del registro, y no se mezclan.
        eventos = [evento for resultado in resultados for evento in _etiquetar(resultado)]

        # Las métricas salen de los eventos (metricas_planificacion). Aquí
        # solo se empaquetan en el diccionario del contrato.
        comparacion = ComparacionAlgoritmos.desde_resultados(resultados)
        metricas: dict[str, object] = {
            "escenario": escenario.name,
            "procesos": len(carga.procesos),
            "algoritmos": {m.algoritmo: m.fila() for m in comparacion.metricas},
        }
        if len(resultados) > 1:
            metricas["mejor"] = {
                "espera_media": comparacion.mejor("espera_media"),
                "respuesta_media": comparacion.mejor("respuesta_media"),
            }

        if config.exportar:
            try:
                ruta_csv, ruta_json = exportar_comparacion(comparacion, escenario, config.directorio_resultados)
            except OSError as error:
                # La simulación ya terminó bien: perderla por un disco o una
                # ruta mala sería peor que entregarla con el error anotado.
                errores.append(f"no se pudo exportar: {error}")
            else:
                exportado = {"csv": str(ruta_csv), "json": str(ruta_json)}
                # El gráfico es un extra del CSV y el JSON. Si falta matplotlib
                # o no se puede escribir el PNG, esos dos archivos ya existen y
                # se conservan: solo se anota el error.
                try:
                    exportado["grafico"] = str(
                        graficar_comparacion(comparacion, escenario, config.directorio_resultados)
                    )
                except (OSError, ImportError) as error:
                    errores.append(f"no se pudo graficar: {error}")
                metricas["exportado"] = exportado

        estado = COMPLETADO_CON_ERRORES if errores else COMPLETADO
        return ModuleResult(NOMBRE, estado, tuple(eventos), metricas, tuple(errores))
