# SO-Sim

SO-Sim es un simulador modular de mecanismos de sistemas operativos aplicado a un escenario ficticio de matrícula universitaria. El proyecto ejecuta algoritmos reproducibles sobre solicitudes de prueba; no procesa matrículas reales ni controla un sistema operativo.

## Alcance

El simulador reúne siete módulos: procesos, hilos y planificación; sincronización; paginación; gestión de memoria contigua; entrada/salida y sistema de archivos; seguridad; y comunicación distribuida simulada.

Los módulos 3 y 4 representan modelos distintos. Paginación traduce direcciones lógicas, administra marcos y compara FIFO, LRU y Óptimo. Gestión de memoria contigua asigna bloques a procesos y calcula fragmentación. No comparten el mismo mapa de memoria.

## Estado del proyecto

Estado a 11 de octubre de 2026.

| Módulo | Contenido | Responsable | Estado |
| --- | --- | --- | --- |
| 1 | Procesos, hilos y planificación | Renato | **Cerrado.** Ver [Módulo 1](#módulo-1-procesos-hilos-y-planificación-cerrado) |
| 2 | Sincronización de procesos | Kike | Implementado en C. Tiene un error de compilación, ver [Problemas conocidos](#problemas-conocidos) |
| 3 | Paginación y reemplazo de páginas | Gabriel | En curso, en la rama `feature/modulo3-paginacion`, sin fusionar |
| 4 | Gestión de memoria contigua y fragmentación | Adán | Implementado y fusionado |
| 5 | Entrada/salida y sistema de archivos | Pendiente | Esqueleto |
| 6 | Seguridad | Pendiente | Esqueleto |
| 7 | Sistemas distribuidos | Pendiente | Esqueleto |

## Arquitectura

`main.py` es el punto de entrada. Tiene los subcomandos `cargar` (valida un escenario y lo muestra) y `procesos` (ejecuta el Módulo 1). Cuando se conecten más módulos, el orquestador cargará un escenario, llamará a cada uno y reunirá sus resultados.

`core/` contiene los modelos y contratos compartidos (`Proceso`, `Evento`, `SimulationConfig`, `ModuleResult` y el protocolo `ModuloSimulacion`), el reloj lógico, la carga y validación de escenarios y las métricas comunes. Cada módulo depende de esos contratos; `core/` no importa módulos concretos y los módulos no se importan entre sí. Pruebas automáticas vigilan que `core/` y el Módulo 1 respeten esas dos reglas.

Cada módulo expone una operación `ejecutar(config)` que devuelve un `ModuleResult` con estado, eventos, métricas y errores recuperables. Hoy solo el Módulo 1 cumple ese contrato; los módulos 2 y 4 usan estructuras propias y se adaptarán después.

La estructura completa y los límites de cada carpeta están en [`docs/arquitectura.md`](docs/arquitectura.md). Las decisiones de diseño se registran en `docs/decisiones/`.

## Módulo 1: procesos, hilos y planificación (cerrado)

El Módulo 1 simula la gestión de procesos de un sistema operativo y la compara con la de uno real.

- **Planificación de CPU** en Python: FCFS, SJF y Prioridad sin expropiación, y Round Robin con quantum configurable. Calculan espera, retorno y respuesta, utilización de CPU, throughput y cambios de contexto, con un coste de cambio de contexto opcional. Producen un diagrama de Gantt en ASCII y un log por evento.
- **Ciclo de vida de un proceso:** el bloque de control (PCB), sus cinco estados y una tabla de procesos con una sola CPU.
- **Comparación de algoritmos** sobre el mismo escenario, con exportación a CSV, JSON y un gráfico de barras PNG.
- **Procesos e hilos POSIX en C:** `fork`, `execvp` y `waitpid` con salida distinta de cero, señal y cero zombis; y un hilo `pthread` por curso, con una demostración de carrera de datos.
- **Contrato común:** el adaptador `ModuloProcesos` devuelve un `ModuleResult`. Los errores del escenario quedan en `errores` y en el estado, nunca se pierden.

Con `escenarios/lote_pequeno.csv`, la espera media es 5.25 en FCFS, 3.75 en SJF, 4.00 en Prioridad y 7.00 en Round Robin con quantum 2. La discusión completa, con el efecto convoy, la inanición y el compromiso del quantum, está en [`IMPLEMENTATIONS.md`](modulo1_procesos/docs/IMPLEMENTATIONS.md). El plan por fases y su estado final están en [`WORKPLAN.md`](modulo1_procesos/docs/WORKPLAN.md).

### Cómo ejecutarlo

Desde la raíz del repositorio:

```bash
python main.py cargar                                          # valida y muestra lote_pequeno.csv
python main.py procesos                                        # los cuatro algoritmos y la tabla comparativa
python main.py procesos --algoritmo RR --quantum 3 --cambio-contexto 1
python main.py procesos --escenario escenarios/lote_grande.csv
python main.py procesos --exportar                             # CSV, JSON y PNG en resultados/
python -m modulo1_procesos.py.cli --algoritmo FCFS --verbose   # Gantt ASCII y log por evento
```

Los mismos comandos como objetivos de `make`:

```bash
make cargar
make procesos
make planificacion ALGORITMO=SJF
make comparacion
make procesos-c
```

Los programas en C se compilan y comprueban desde su carpeta:

```bash
make -C modulo1_procesos/c all
make -C modulo1_procesos/c sanitize
make -C modulo1_procesos/c werror
make -C modulo1_procesos/c hilos-tsan
```

`sanitize` compila con AddressSanitizer y UndefinedBehaviorSanitizer, `hilos-tsan` con ThreadSanitizer y `werror` convierte cada advertencia en un error. Valgrind está cubierto por pruebas que se omiten si no está instalado.

### Alcance del cierre

El módulo cumple los objetivos del plan. Quedan fuera, y no bloquean el cierre, el envejecimiento (aging) para Prioridad y el material de sustentación. El detalle está en la sección final de `WORKPLAN.md`.

## Requisitos

- Python 3.11 o superior.
- GCC y GNU Make para los componentes C.
- Linux o WSL para compilar y ejecutar llamadas POSIX como `fork`, `exec`, `wait`, pthreads y semáforos.
- `matplotlib` para el gráfico del Módulo 1. Sin él, el resto funciona y la exportación avisa de que no pudo graficar.
- Valgrind, opcional.

Las dependencias Python están en `requirements.txt`. La guía [`docs/instalacion_y_ejecucion.md`](docs/instalacion_y_ejecucion.md) detalla la instalación en Linux, WSL y PowerShell, y todos los comandos.

## Instalación en PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Linux o WSL, crea el entorno con `python3 -m venv .venv`, actívalo con `source .venv/bin/activate` e instala las dependencias con `python -m pip install -r requirements.txt`.

## Pruebas

`make test` ejecuta toda la suite con `pytest`. Las pruebas que necesitan `gcc`, `make`, `matplotlib` o `valgrind` se omiten si falta la herramienta.

## Problemas conocidos

- **Módulo 2:** `modulo2_sincronizacion/c/lectores_escritores.c` tiene comentada la línea `// #include <semaphore.h>` (línea 53). El archivo no compila, y por eso fallan 1 prueba y 23 más tienen error en `tests/test_sincronizacion.py`. El resto de la suite pasa.
