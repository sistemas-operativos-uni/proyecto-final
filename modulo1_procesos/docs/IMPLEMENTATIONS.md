# Módulo 1: registro de implementaciones

Responsable: Renato. Rama: `feature/renato-procesos-planificacion`.

Este archivo registra lo que existe en el Módulo 1 y discute lo que miden sus algoritmos. Las cifras salen del simulador. La prueba `tests/test_documentacion_modulo1.py` recalcula cada fila de las tablas y falla si el documento deja de coincidir con el código.

## Qué hay implementado

| Fase | Contenido | Archivos | Cómo verlo |
| --- | --- | --- | --- |
| 0 | Modelos, contrato, reloj lógico, cargador de escenarios, métricas comunes | `core/*.py`, `main.py` | `make cargar` |
| 1 | PCB, estados y tabla de procesos con una sola CPU | `py/pcb.py` | `tests/test_procesos.py` |
| 2 | Procesos POSIX: `fork`, `execvp`, `waitpid`, salida distinta de cero, señal, cero zombis | `c/crear_proceso.c` | `make procesos-c` |
| 3 | Hilos POSIX por curso y demostración de carrera de datos con ThreadSanitizer | `c/hilos.c` | `make procesos-c`, `make -C modulo1_procesos/c hilos-tsan` |
| 4 | FCFS, SJF y Prioridad sin expropiación, Gantt ASCII y log por evento | `py/motor.py`, `py/fcfs.py`, `py/sjf.py`, `py/prioridad.py`, `py/diagrama.py` | `make planificacion` |
| 5 | Round Robin, cola FIFO, cambios de contexto y su coste | `py/round_robin.py` | `make planificacion ALGORITMO=RR` |
| 6 | Métricas derivadas de los eventos, comparación, CSV, JSON y gráfico | `py/metricas_planificacion.py`, `py/graficos.py`, `py/cli.py` | `make comparacion` |
| 7 | Adaptador al contrato `ModuleResult` y subcomando `main.py procesos` | `py/adaptador.py` | `make procesos` |
| 8 | Escenarios límite, ASan y UBSan, Valgrind y `-Werror` sobre los programas en C, README y guía de instalación | `tests/test_escenarios_limite.py`, `c/Makefile`, `README.md` | `make -C modulo1_procesos/c sanitize`, `make -C modulo1_procesos/c werror` |

El módulo está cerrado. Quedan fuera del cierre el envejecimiento (aging) opcional para Prioridad y el material de sustentación; el estado completo está al inicio de `WORKPLAN.md`.

## Cómo reproducir las cifras

```bash
make planificacion ESCENARIO=escenarios/lote_pequeno.csv
make planificacion ESCENARIO=escenarios/lote_grande.csv
make planificacion ALGORITMO=RR QUANTUM=3 CAMBIO_CONTEXTO=1
make comparacion            # CSV, JSON y gráfico en resultados/
```

## Datos de partida

- `lote_pequeno.csv`: 4 procesos con ráfagas 5, 3, 7 y 2. Suman 17 unidades.
- `lote_grande.csv`: 10 procesos con ráfagas 5, 3, 7, 4, 6, 2, 8, 3, 5 y 4. Suman 47 unidades y llegan entre t=0 y t=9.
- La unidad de tiempo es abstracta. Una prioridad menor significa más prioridad.
- Round Robin usa quantum 2 salvo en la tabla del quantum.
- El coste de cambio de contexto vale 0, salvo en la última columna de la tabla del quantum, donde cada cambio cuesta 1 unidad.

## Comparación general

**lote_pequeno**

| Algoritmo | Espera media | Retorno medio | Respuesta media | Cambios de contexto |
| --- | --- | --- | --- | --- |
| FCFS | 5.25 | 9.50 | 5.25 | 3 |
| SJF | 3.75 | 8.00 | 3.75 | 3 |
| PRIORIDAD | 4.00 | 8.25 | 4.00 | 3 |
| RR(q=2) | 7.00 | 11.25 | 1.75 | 8 |

**lote_grande**

| Algoritmo | Espera media | Retorno medio | Respuesta media | Cambios de contexto |
| --- | --- | --- | --- | --- |
| FCFS | 17.00 | 21.70 | 17.00 | 9 |
| SJF | 12.50 | 17.20 | 12.50 | 9 |
| PRIORIDAD | 13.70 | 18.40 | 13.70 | 9 |
| RR(q=2) | 23.90 | 28.60 | 7.10 | 25 |

SJF gana en espera y retorno en los dos lotes. Round Robin gana en respuesta (1.75 y 7.10) y pierde en espera: en `lote_grande` su espera media (23.90) supera a la de FCFS (17.00). También hace más cambios de contexto: 8 y 25, frente a 3 y 9.

Sin expropiación, la respuesta es igual a la espera, porque un proceso que entra a la CPU corre hasta terminar. Por eso FCFS, SJF y Prioridad repiten la misma cifra en las dos columnas.

## Efecto convoy en FCFS

FCFS atiende por orden de llegada y no mira la duración. Un proceso largo que llega antes retrasa a todos los que vienen detrás, aunque necesiten muy poca CPU. Ese retraso en cadena es el efecto convoy.

En `lote_pequeno`, P003 (ráfaga 7) llega en t=2 y se ejecuta antes que P004 (ráfaga 2), que llega en t=4. P004 espera 11 unidades para usar 2, es decir 5.5 veces su ráfaga. Con SJF espera 1.

En `lote_grande` el efecto es más fuerte. P006 (ráfaga 2) llega en t=5 con cinco procesos por delante, de P001 a P005, que suman 25 unidades de ráfaga. Espera 20. Con SJF espera 0.

**Espera de los procesos con ráfaga de 3 o menos**

*lote_pequeno*

| Proceso | Ráfaga | Espera en FCFS | Espera en SJF |
| --- | --- | --- | --- |
| P002 | 3 | 4 | 6 |
| P004 | 2 | 11 | 1 |

*lote_grande*

| Proceso | Ráfaga | Espera en FCFS | Espera en SJF |
| --- | --- | --- | --- |
| P002 | 3 | 4 | 6 |
| P006 | 2 | 20 | 0 |
| P008 | 3 | 28 | 3 |

| Escenario | Espera media en FCFS | Espera media en SJF |
| --- | --- | --- |
| lote_pequeno | 7.50 | 3.50 |
| lote_grande | 17.33 | 3.00 |

El convoy no castiga a todos por igual. P002 espera más con SJF (6 contra 4) porque SJF adelanta a P004, que es más corto. En `lote_grande` P002 pierde 2 unidades y P008 gana 25. SJF mueve la espera de los procesos cortos a los largos, y la suma baja: la espera media pasa de 5.25 a 3.75 en `lote_pequeno` y de 17.00 a 12.50 en `lote_grande`.

FCFS tiene sus ventajas: no hay inanición, el orden se explica en una frase y no necesita saber la ráfaga de antemano. El convoy es el precio de esa simplicidad.

## Inanición en SJF y Prioridad

SJF elige la ráfaga más corta y Prioridad elige el número de prioridad más bajo. Con los dos, un proceso largo o de baja prioridad cede su turno cada vez que llega alguien mejor. Si llegan sin parar, espera sin límite. Eso es inanición.

### Lo que muestran los lotes reales

Los lotes reales no producen inanición, porque el flujo de llegadas termina. Muestran dónde cae la espera más larga:

**lote_pequeno**

| Algoritmo | Proceso con mayor espera | Ráfaga | Prioridad | Espera |
| --- | --- | --- | --- | --- |
| FCFS | P004 | 2 | 2 | 11 |
| SJF | P003 | 7 | 3 | 8 |
| PRIORIDAD | P003 | 7 | 3 | 8 |

**lote_grande**

| Algoritmo | Proceso con mayor espera | Ráfaga | Prioridad | Espera |
| --- | --- | --- | --- | --- |
| FCFS | P010 | 4 | 1 | 34 |
| SJF | P007 | 8 | 3 | 33 |
| PRIORIDAD | P009 | 5 | 4 | 34 |

Con FCFS, la espera más larga recae en un proceso que llegó tarde, sea corto o largo. Con SJF recae en el proceso de mayor ráfaga: P003 (7) en `lote_pequeno` y P007 (8) en `lote_grande`. Con Prioridad recae en la prioridad 3 en `lote_pequeno` y en la prioridad 4, la más baja, en `lote_grande`. SJF y Prioridad no reducen el peor caso. En `lote_grande` la espera máxima apenas cambia (34, 33 y 34); lo que cambia es quién la sufre.

### Un escenario sintético que sí produce inanición

Los lotes del repositorio no sirven para ver la inanición, así que este escenario es sintético y se construyó para eso. P000 corre de 0 a 2. PLARGO llega en t=1 con ráfaga 20 y prioridad 9. Desde t=2 llega un proceso corto (ráfaga 2, prioridad 1) cada 2 unidades, justo cuando termina el anterior, así que siempre hay uno listo. Son 15 procesos cortos.

| Algoritmo | Espera de PLARGO | Espera media de los 15 cortos |
| --- | --- | --- |
| FCFS | 1 | 20.00 |
| SJF | 31 | 0.00 |
| PRIORIDAD | 31 | 0.00 |

Con SJF y Prioridad, PLARGO no corre hasta que pasa el último corto, en t=32, y termina en t=52. Los 15 cortos no esperan nada. Con FCFS ocurre lo contrario: PLARGO espera 1 y cada corto espera 20 unidades.

Aquí la espera de PLARGO (31) depende de cuántos cortos lleguen. El flujo es finito, así que PLARGO termina. Si los cortos siguieran llegando cada 2 unidades, PLARGO esperaría mientras llegaran.

### Mitigación

El envejecimiento (aging) sube la prioridad de un proceso según el tiempo que lleva esperando, y con eso acota la espera. El Módulo 1 todavía no lo implementa; está previsto como mejora opcional en la Fase 8. Hoy SJF y Prioridad cargan con el riesgo.

## El compromiso del quantum en Round Robin

El quantum fija cuánto corre un proceso antes de ceder la CPU. Un quantum pequeño reparte la CPU en turnos cortos y baja la respuesta, y cada turno extra cuesta un cambio de contexto. Un quantum mayor que la ráfaga más larga hace que Round Robin se comporte como FCFS.

La última columna usa un coste de 1 unidad por cambio de contexto. Mide cuánto del tiempo total ocupa trabajo útil. Las otras columnas usan coste 0.

**lote_pequeno**

| Quantum | Espera media | Respuesta media | Cambios de contexto | Utilización con coste 1 (%) |
| --- | --- | --- | --- | --- |
| 1 | 6.50 | 0.75 | 13 | 56.7 |
| 2 | 7.00 | 1.75 | 8 | 68.0 |
| 3 | 5.75 | 3.25 | 5 | 77.3 |
| 5 | 5.25 | 4.75 | 4 | 81.0 |
| 8 | 5.25 | 5.25 | 3 | 85.0 |
| 100 | 5.25 | 5.25 | 3 | 85.0 |

**lote_grande**

| Quantum | Espera media | Respuesta media | Cambios de contexto | Utilización con coste 1 (%) |
| --- | --- | --- | --- | --- |
| 1 | 23.90 | 3.60 | 44 | 51.1 |
| 2 | 23.90 | 7.10 | 25 | 65.3 |
| 3 | 22.40 | 9.80 | 18 | 72.3 |
| 5 | 20.60 | 14.20 | 12 | 79.7 |
| 8 | 17.00 | 17.00 | 9 | 83.9 |
| 100 | 17.00 | 17.00 | 9 | 83.9 |

Lo que muestran las tablas:

- **La respuesta mejora al bajar el quantum.** En `lote_grande` pasa de 17.00 (quantum 8 o más) a 3.60 (quantum 1). En `lote_pequeno`, de 5.25 a 0.75.
- **El precio son los cambios de contexto.** En `lote_grande` suben de 9 a 44. Con un coste de 1 unidad por cambio, la utilización cae de 83.9 % a 51.1 %: casi la mitad del tiempo se va en cambiar de proceso.
- **La espera media no sigue el quantum en línea recta.** En `lote_pequeno` va 6.50, 7.00, 5.75, 5.25. El quantum 2 es peor que el 1 y el 3. En `lote_grande` es igual con quantum 1 y 2 (23.90) y baja después.
- **Con un quantum de 8 o más, el resultado es el de FCFS.** En `lote_grande` la ráfaga mayor es 8; en `lote_pequeno` es 7. Con quantum 100, las dos tablas dan los valores de FCFS: espera 5.25 y 17.00, y 3 y 9 cambios.
- **En estos dos lotes, ningún quantum baja la espera media por debajo de FCFS.** Ni de la de SJF (3.75 y 12.50). Round Robin se elige por la respuesta, y la espera media no es su ventaja.

Un quantum de 2 queda en medio: respuesta aceptable (1.75 y 7.10) y un coste alto (8 y 25 cambios). Para un uso interactivo, donde importa que nadie espere mucho para recibir la primera atención, conviene un quantum pequeño. Para trabajo por lotes, donde importa terminar todo pronto, conviene uno grande o FCFS y SJF.

## Límites de estas mediciones

- Los lotes tienen 4 y 10 procesos. Las comparaciones ilustran el comportamiento, no son una muestra estadística.
- Ningún proceso pide entrada/salida ni se bloquea. Un sistema real mezcla procesos limitados por CPU y por E/S, y eso cambia el orden de los algoritmos.
- Hay una sola CPU y todos los tiempos son abstractos.
- El coste de 1 unidad por cambio de contexto es una elección del proyecto. Un coste real depende de la máquina.
- El escenario de inanición es sintético y se construyó para provocarla.
