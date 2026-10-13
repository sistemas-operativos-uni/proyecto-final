"""Experimento reproducible: compara estrategias y tamaños de paquete.

Genera 100 jornadas aleatorias (semillas 1 a 100). Cada jornada tiene 300
operaciones: 60 % de probabilidad de que llegue un proceso nuevo (pide entre
16 y 256 KB) y 40 % de que termine uno de los procesos vivos, elegido al azar.
Las tres estrategias reciben exactamente la misma secuencia de operaciones.

Un proceso rechazado no se reintenta (no hay cola de espera).

Uso desde la raíz del repositorio::

    python -m modulo4_memoria.py.experimento
    python -m modulo4_memoria.py.experimento --salida modulo4_memoria/docs/EXPERIMENTO.md
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from .asignacion_contigua import ESTRATEGIAS, MemoriaContigua, SinEspacioError
from .fragmentacion import medir

SEMILLAS = range(1, 101)
PASOS = 300
TOTAL_KB = 1024
UNIDADES = (1, 16, 32, 64, 128)


def generar_carga(semilla: int, pasos: int = PASOS) -> list[tuple[str, float]]:
    """Secuencia de operaciones; con la misma semilla siempre sale la misma."""
    rng = random.Random(semilla)
    operaciones = []
    for _ in range(pasos):
        if rng.random() < 0.6:
            operaciones.append(("asignar", rng.randint(16, 256)))
        else:
            operaciones.append(("liberar", rng.random()))
    return operaciones


def correr_jornada(estrategia: str, operaciones, total_kb: int, unidad_kb: int) -> dict:
    memoria = MemoriaContigua(total_kb, unidad_kb)
    vivos: list[str] = []
    pedidos = rechazos = rechazos_frag = 0
    externa, interna, huecos = [], [], []
    for numero, (operacion, valor) in enumerate(operaciones, start=1):
        if operacion == "asignar":
            pedidos += 1
            proceso_id = f"P{numero}"
            try:
                memoria.asignar(proceso_id, int(valor), estrategia)
                vivos.append(proceso_id)
            except SinEspacioError as error:
                rechazos += 1
                rechazos_frag += error.por_fragmentacion
        elif vivos:
            memoria.liberar(vivos.pop(int(valor * len(vivos))))
        reporte = medir(memoria.bloques)
        externa.append(reporte.externa.porcentaje)
        interna.append(reporte.interna.porcentaje)
        huecos.append(reporte.externa.cantidad_huecos)
    n = len(operaciones)
    return {
        "pedidos": pedidos, "rechazos": rechazos, "rechazos_frag": rechazos_frag,
        "externa": sum(externa) / n, "interna": sum(interna) / n, "huecos": sum(huecos) / n,
    }


def resumir(estrategia: str, unidad_kb: int, total_kb: int = TOTAL_KB) -> dict:
    acumulado = dict(pedidos=0, rechazos=0, rechazos_frag=0, externa=0.0, interna=0.0, huecos=0.0)
    for semilla in SEMILLAS:
        resultado = correr_jornada(estrategia, generar_carga(semilla), total_kb, unidad_kb)
        for clave in acumulado:
            acumulado[clave] += resultado[clave]
    jornadas = len(SEMILLAS)
    return {
        "pedidos": acumulado["pedidos"],
        "rechazos_pct": 100 * acumulado["rechazos"] / acumulado["pedidos"],
        "rechazos_frag_x100": 100 * acumulado["rechazos_frag"] / acumulado["pedidos"],
        "externa": acumulado["externa"] / jornadas,
        "interna": acumulado["interna"] / jornadas,
        "huecos": acumulado["huecos"] / jornadas,
    }


def _f(numero: float, decimales: int = 1) -> str:
    return f"{numero:.{decimales}f}".replace(".", ",")


def informe() -> str:
    lineas = [
        "# Experimento del Módulo 4",
        "",
        "Generado con `python -m modulo4_memoria.py.experimento`.",
        f"{len(SEMILLAS)} jornadas aleatorias (semillas 1–100) × {PASOS} operaciones, "
        f"memoria de {TOTAL_KB} KB. Un rechazo no se reintenta.",
        "",
        "## 1. Estrategias (paquete de 64 KB, misma carga para las tres)",
        "",
        "| Métrica | " + " | ".join(ESTRATEGIAS) + " |",
        "|---|" + "---:|" * len(ESTRATEGIAS),
    ]
    datos = {e: resumir(e, 64) for e in ESTRATEGIAS}
    filas = [
        ("Procesos que pidieron memoria", "pedidos", lambda v: str(v)),
        ("Rechazados aunque había memoria, cada 100", "rechazos_frag_x100", _f),
        ("Rechazados en total (%)", "rechazos_pct", _f),
        ("Fragmentación externa promedio (%)", "externa", _f),
        ("Fragmentación interna promedio (%)", "interna", _f),
        ("Huecos separados (promedio)", "huecos", lambda v: _f(v, 2)),
    ]
    for titulo, clave, formato in filas:
        lineas.append(f"| {titulo} | " + " | ".join(formato(datos[e][clave]) for e in ESTRATEGIAS) + " |")
    lineas += [
        "",
        "## 2. Tamaño del paquete (estrategia mejor ajuste)",
        "",
        "| Paquete (KB) | Interna (%) | Externa (%) | Rechazados en total (%) |",
        "|---:|---:|---:|---:|",
    ]
    for unidad in UNIDADES:
        r = resumir("mejor", unidad)
        lineas.append(f"| {unidad} | {_f(r['interna'])} | {_f(r['externa'])} | {_f(r['rechazos_pct'])} |")
    return "\n".join(lineas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path, help="archivo .md donde guardar el informe")
    args = parser.parse_args()
    texto = informe()
    print(texto)
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    main()
