# SO-Sim

SO-Sim es un simulador modular de mecanismos de sistemas operativos aplicado a un escenario ficticio de matrícula universitaria. El proyecto ejecuta algoritmos reproducibles sobre solicitudes de prueba; no procesa matrículas reales ni controla un sistema operativo.

## Alcance

El simulador reúne siete módulos: procesos, hilos y planificación; sincronización; paginación; gestión de memoria contigua; entrada/salida y sistema de archivos; seguridad; y comunicación distribuida simulada.

Los módulos 3 y 4 representan modelos distintos. Paginación traduce direcciones lógicas, administra marcos y compara FIFO, LRU y Óptimo. Gestión de memoria contigua asigna bloques a procesos y calcula fragmentación. No comparten el mismo mapa de memoria.

## Responsables

- Módulo 1, procesos, hilos y planificación: Renato.
- Módulo 2, sincronización de procesos: Kike.
- Módulo 3, paginación y reemplazo de páginas: Gabriel.
- Módulo 4, gestión de memoria contigua y fragmentación: Adán.
- Módulos 5, 6 y 7: responsables pendientes de asignación por el equipo.

## Arquitectura

`main.py` será el punto de entrada. El orquestador cargará un escenario, llamará a cada módulo y reunirá sus resultados. `core/` mantendrá los modelos y contratos compartidos, el reloj lógico, las métricas comunes y la carga de escenarios. Cada módulo dependerá de esos contratos; `core/` no importará módulos concretos. Los módulos no se importarán entre sí.

Cada módulo expondrá una operación de ejecución con configuración de entrada y un resultado estructurado. El resultado incluirá estado, eventos, métricas y errores recuperables. Los nombres y campos comunes se definirán en `core/modelos.py` y `core/contratos.py` antes de implementar las simulaciones.

La estructura completa y los límites de cada carpeta están en [`docs/arquitectura.md`](docs/arquitectura.md). Las decisiones de diseño se registran en `docs/decisiones/`.

## Requisitos

- Python 3.11 o superior.
- GCC y GNU Make para los componentes C.
- Linux o WSL para compilar y ejecutar llamadas POSIX como `fork`, `exec`, `wait`, pthreads y semáforos.

Las dependencias Python están en `requirements.txt`. Los archivos C y Python de esta estructura son esqueletos comentados; todavía no implementan algoritmos ni ofrecen una ejecución funcional.

## Instalación en PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Linux o WSL, crea el entorno con `python3 -m venv .venv`, actívalo con `source .venv/bin/activate` e instala las dependencias con `python -m pip install -r requirements.txt`.

## Estado inicial

Esta carpeta contiene la arquitectura, los escenarios iniciales, la documentación, la configuración y archivos fuente comentados. El equipo implementará cada módulo, añadirá sus pruebas y activará los comandos de ejecución cuando exista una versión funcional.
