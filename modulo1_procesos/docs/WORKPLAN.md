# Módulo 1: plan de trabajo (Procesos, hilos y planificación)

Responsable: Renato. Rama: `feature/renato-procesos-planificacion`.

## 1. Diagnóstico del repositorio (11 de octubre de 2026)

Revisadas `main`, `origin/feature/modulo3-paginacion`, `origin/feature/modulo4-memoria` y la rama actual.

| Pieza | Estado | Evidencia |
| --- | --- | --- |
| Módulo 1 (`py/*.py`, `c/crear_proceso.c`, `c/hilos.c`) | **Solo esqueletos**: una línea de comentario por archivo, sin código | 1–2 líneas por archivo en todas las ramas |
| `core/` (`modelos`, `contratos`, `metricas`, `reloj`, `cargador_escenarios`) | **Solo esqueletos** y es responsabilidad de Renato (ver `docs/arquitectura.md`) | 1 línea por archivo |
| `main.py` | Esqueleto, no ejecuta nada | 1 línea |
| Módulo 2 (sincronización, C) | Implementado en `main` (`lectores_escritores.c` 689 líneas, `semaforos.c` 399) con pruebas | `tests/test_sincronizacion.py` |
| Módulo 3 (paginación) | Parcial, **solo en `feature/modulo3-paginacion`**, sin fusionar a `main` | `gestor_paginacion.py` 131 líneas |
| Módulo 4 (memoria contigua) | Implementado y fusionado en `main` (PR #1) | 561 líneas de código + 366 de pruebas |
| Módulos 5, 6, 7 | Esqueletos (fuera del 50 % del parcial) | — |

Archivos de inicialización: **existen** los `__init__.py` de cada paquete, `Makefile` raíz, `pytest.ini`, `requirements.txt`, escenarios CSV y los `Makefile` de cada carpeta C. **No están implementados** los contratos de `core/` ni el punto de entrada `main.py`, y el `Makefile` de `modulo1_procesos/c` no produce ejecutables.

Cambio local pendiente: `crear_proceso.c` (comentario reescrito sin `/* */`). Se sustituye en la Fase 2.

### Dependencias que bloquean a otros módulos

El Módulo 4 ya declara pendiente "adaptar `ResultadoMemoria` a `ModuleResult` cuando Renato defina `core/modelos.py` y `core/contratos.py`". El Módulo 3 tampoco tiene contrato. **La Fase 0 de este plan desbloquea a todo el equipo y va primero.**

## 2. Alcance y decisiones de diseño

- **Python** para la planificación (FCFS, SJF, Round Robin, Prioridad). **C/POSIX** para `fork`/`exec`/`wait` e hilos `pthread` (según `PROYECTO-SO.md`).
- Arquitectura por capas de `docs/arquitectura.md`: el módulo importa `core/`, nunca otros módulos; los algoritmos devuelven datos y **no imprimen**. La CLI es la única capa que formatea logs.
- Un algoritmo = una función pura `(procesos, config) -> ResultadoPlanificacion`. Patrón Strategy mediante un registro en `planificador.py`.
- Convenciones fijas (se prueban, para que los resultados sean reproducibles):
  - Prioridad: **menor número = mayor prioridad** (P002 con `prioridad=1` es la más urgente en `lote_pequeno.csv`). No expropiativa; con la opción `--expropiativa` como mejora de la Fase 8.
  - SJF no expropiativo. Desempate: llegada, luego `id`.
  - Round Robin: si un proceso llega en el mismo instante en que otro agota su quantum, **el que llega entra a la cola primero**.
  - CPU ociosa: el reloj salta a la siguiente llegada y se registra el hueco como `OCIOSA`.
  - Cambio de contexto: coste configurable (`--cambio-contexto N`, por defecto 0) y se cuenta siempre.
- Desarrollo con TDD: cada fase empieza con la prueba que falla (rojo), luego la implementación mínima (verde), luego refactor.

## 3. Estructura objetivo

```text
modulo1_procesos/
├── docs/WORKPLAN.md              este archivo
├── docs/IMPLEMENTATIONS.md       registro por fase (se crea al cerrar la Fase 1)
├── py/
│   ├── pcb.py                    PCB, estados y transiciones válidas
│   ├── fcfs.py  sjf.py  prioridad.py  round_robin.py
│   ├── planificador.py           registro de algoritmos + comparación
│   ├── metricas_planificacion.py espera, retorno, respuesta, CPU, throughput
│   ├── diagrama.py               Gantt ASCII a partir de los eventos
│   └── cli.py                    `python -m modulo1_procesos.py.cli`
└── c/
    ├── crear_proceso.c           fork / exec / wait
    ├── hilos.c                   pthread_create / pthread_join
    └── Makefile
tests/test_procesos.py   tests/test_planificacion.py   tests/test_hilos_c.py
```

## 4. Contrato de logs

Todo log es **salida de consola reproducible** con el mismo formato y el prefijo `[modulo1]`. Cada fase define qué log demuestra su resultado y un criterio de aceptación verificable. Nivel `--verbose` imprime cada evento; sin él, solo el resumen.

```text
[modulo1][t=005] FCFS  P002  LISTO -> EJECUCION  (espera=4)
[modulo1][t=008] FCFS  P002  EJECUCION -> TERMINADO
```

Campos de evento: `instante`, `modulo="procesos"`, `entidad` (id del proceso), `accion`, `datos` (compatible con el `Evento` ya usado en el Módulo 4).

## 5. Fases

### Fase 0: Fundaciones de `core/` (bloqueante, 1ª)

Objetivo: contratos compartidos que el Módulo 3 y el Módulo 4 esperan.

- [x] `core/modelos.py`: `Proceso` (id, llegada, ráfaga, prioridad, memoria_kb, cursos), `Evento`, `SimulationConfig`, `ModuleResult` (estado, eventos, métricas, errores). Datos inmutables (`dataclass(frozen=True, slots=True)`).
- [x] `core/contratos.py`: `Protocol` de módulo ejecutable (`ejecutar(config) -> ModuleResult`).
- [x] `core/reloj.py`: reloj lógico monótono (`avanzar`, `saltar_a`), no retrocede.
- [x] `core/cargador_escenarios.py`: lee y **valida** `lote_pequeno.csv` / `lote_grande.csv` (columnas, enteros, ráfaga > 0, llegada ≥ 0, ids únicos); errores explícitos, sin fallos silenciosos.
- [x] `core/metricas.py`: promedio y exportación a CSV/JSON en `resultados/`.
- [x] `main.py`: parser con subcomando `procesos` (se completa en la Fase 7).
- [ ] Aviso al equipo (Gabriel y Adán) con los nombres de campos finales.

Pruebas primero: `tests/test_core.py` (CSV válido, columna faltante, ráfaga 0, id duplicado, reloj no retrocede).

**Log de la fase:**

```text
[core] escenario=lote_pequeno.csv procesos=4 validación=OK
 id    llegada rafaga prio mem_kb cursos
 P001  0       5      2    128    SO101;BD202
 ...
```

**Aceptación:** `pytest tests/test_core.py` en verde; el Módulo 4 puede importar `ModuleResult`.

### Fase 1: Modelo de proceso: PCB y diagrama de estados

Objetivo: el estado de un proceso se modela una sola vez y todos los algoritmos lo reutilizan.

- [x] `PCB`: pid, estado, prioridad, llegada, ráfaga total y restante, `t_primera_cpu`, `t_fin`. No hay `t_inicio` aparte: coincidiría con `t_primera_cpu`.
- [x] Estados `NUEVO → LISTO → EJECUCION → (BLOQUEADO →) LISTO → TERMINADO`.
- [x] Tabla de transiciones válidas; una transición inválida lanza `TransicionInvalida` (fail fast).
- [x] Invariantes: ráfaga restante ≥ 0; `TERMINADO` solo con restante = 0; un único proceso en `EJECUCION` por CPU (esta última la aplica `TablaProcesos`, que también emite un `Evento` por transición).

Pruebas primero: transiciones válidas e inválidas, invariantes, `PCB` creado desde `Proceso`.

**Log de la fase:** línea de vida de cada proceso.

```text
[modulo1][t=000] P001 NUEVO -> LISTO
[modulo1][t=000] P001 LISTO -> EJECUCION
[modulo1][t=005] P001 EJECUCION -> TERMINADO
```

**Aceptación:** la secuencia de estados de los 4 procesos de `lote_pequeno.csv` es la esperada.

### Fase 2: Procesos POSIX en C (`crear_proceso.c`)

Objetivo: demostrar el ciclo de vida real de un proceso en el SO anfitrión, contextualizado como "worker de matrícula".

- [ ] `fork()` con manejo de error (`-1`), distinción padre/hijo.
- [ ] El hijo hace `execvp` de un comando simple (`echo`/`date`) y, si falla, sale con `_exit(127)`.
- [ ] El padre usa `waitpid` y decodifica el estado: `WIFEXITED`, `WEXITSTATUS`, `WIFSIGNALED`.
- [ ] Segundo escenario: N hijos ("N solicitudes de matrícula"), el padre recoge a todos; sin zombies.
- [ ] Demostración de un hijo con salida distinta de cero y de un hijo terminado por señal.
- [ ] `Makefile`: objetivos `all`, `run-procesos`, `clean`; compilar con `-Wall -Wextra -Wpedantic`.

Pruebas primero: `tests/test_hilos_c.py` (o `test_procesos.py`) compila con `make` y ejecuta el binario con `subprocess`, comprueba código de salida 0 y líneas clave del log.

**Log de la fase:**

```text
[padre pid=4121] creando 3 hijos
[hijo  pid=4122 ppid=4121] ejecutando: echo matricula P001
[padre] hijo 4122 terminó con estado=0
[padre] hijo 4124 terminado por señal 9 (SIGKILL)
[padre] 3/3 hijos recogidos, 0 zombies
```

**Aceptación:** compila sin warnings; `valgrind`/`ps` muestran 0 zombies; el log lista cada PID y su estado.

### Fase 3: Hilos POSIX en C (`hilos.c`)

Objetivo: demostrar hilos de un mismo proceso con memoria compartida.

- [ ] `pthread_create` / `pthread_join` con comprobación de errores.
- [ ] Un hilo por curso (`SO101`, `BD202`, `ARQ110`) procesa las solicitudes del lote; cada hilo devuelve su resultado por `join`, sin variables globales compartidas escritas.
- [ ] Un caso de contraste (opcional, marcado con `--demo-carrera`) con un contador compartido sin protección frente a la versión con `pthread_mutex_t`, solo para mostrar el problema. La sincronización formal es del Módulo 2.
- [ ] Demostración de la diferencia proceso/hilo: PID compartido, `pthread_self()` distinto.

Pruebas primero: ejecutar con `-fsanitize=thread` y verificar 0 reportes en la versión protegida.

**Log de la fase:**

```text
[main pid=5001] lanzando 3 hilos
[hilo SO101 tid=140211] procesadas 12 solicitudes
[hilo BD202 tid=140212] procesadas 9 solicitudes
[main] join OK; total=31 (esperado=31)
```

**Aceptación:** total esperado = total obtenido en 100 ejecuciones consecutivas; ThreadSanitizer limpio.

### Fase 4: Planificadores no expropiativos (FCFS, SJF, Prioridad)

Objetivo: tres algoritmos sobre el mismo escenario.

- [ ] `fcfs.py`, `sjf.py`, `prioridad.py` con la firma común `(procesos, config) -> ResultadoPlanificacion`.
- [ ] `planificador.py`: registro `ALGORITMOS = {"FCFS": ..., "SJF": ..., "PRIORIDAD": ...}`; nombre desconocido ⇒ error explícito.
- [ ] Manejo de CPU ociosa y de llegadas simultáneas con el desempate documentado.
- [ ] Cada algoritmo emite eventos (`LLEGADA`, `DESPACHO`, `FIN`, `OCIOSA`) y el segmento del Gantt.

Pruebas primero: tabla de oráculo calculada a mano para `lote_pequeno.csv` (espera = inicio − llegada):

| Algoritmo | Orden de ejecución | Espera P001/P002/P003/P004 | Espera media | Retorno medio |
| --- | --- | --- | --- | --- |
| FCFS | P001, P002, P003, P004 | 0 / 4 / 6 / 11 | 5,25 | 9,50 |
| SJF | P001, P004, P002, P003 | 0 / 6 / 8 / 1 | 3,75 | 8,00 |
| Prioridad | P001, P002, P004, P003 | 0 / 4 / 8 / 4 | 4,00 | 8,25 |

Más casos: un solo proceso, todas las llegadas en 0, hueco de CPU ociosa, empate de ráfaga, empate de prioridad, lista vacía.

**Log de la fase (por algoritmo):**

```text
== FCFS | escenario=lote_pequeno.csv ==
Gantt: |P001      |P002   |P003         |P004 |
       0         5       8             15    17
[modulo1][t=000] FCFS P001 despachado (espera=0)
...
```

**Aceptación:** la tabla de oráculo se cumple exactamente; los tres algoritmos ejecutan `lote_grande.csv` sin excepciones.

### Fase 5: Round Robin

Objetivo: el algoritmo expropiativo con quantum.

- [ ] Cola FIFO de listos; `quantum` configurable (> 0, validado).
- [ ] Regla de llegada simultánea fijada en §2; el proceso que agota el quantum vuelve al final de la cola.
- [ ] Contador de cambios de contexto y coste configurable.
- [ ] Primer acceso a CPU por proceso para el tiempo de respuesta.

Pruebas primero: oráculo `lote_pequeno.csv`, quantum 2 → orden P001, P002, P003, P001, P004, P002, P003, P001, P003, P003; finalizan P004 t=10, P002 t=11, P001 t=14, P003 t=17; espera 9/7/8/4 (media 7,00); respuesta 0/1/2/4. Casos: quantum ≥ ráfaga mayor (equivale a FCFS), quantum 1, quantum 0 (error), un proceso.

**Log de la fase:**

```text
[modulo1][t=002] RR(q=2) P001 expropiado (restante=3) -> cola=[P002,P003,P001]
[modulo1][t=014] RR(q=2) P001 terminado
cambios_de_contexto=9
```

**Aceptación:** el oráculo se cumple; con quantum ≥ 7 el resultado es idéntico a FCFS.

### Fase 6: Métricas y comparación cuantitativa

Objetivo: lo que pide la rúbrica ("compara cuantitativamente con gráficos y discusión crítica").

- [ ] `metricas_planificacion.py`: tiempo de espera, retorno, **respuesta**, utilización de CPU, throughput, cambios de contexto, por proceso y promedios.
- [ ] Una sola fuente de verdad: las métricas se derivan de los eventos, no se calculan en cada algoritmo.
- [ ] `comparar_algoritmos()` ejecuta todos con exactamente el mismo escenario.
- [ ] Exportación a `resultados/procesos_<escenario>.csv|json`.
- [ ] Gráfico de barras (espera y retorno por algoritmo) con `matplotlib`, backend `Agg` para no requerir pantalla.
- [ ] Sección de discusión en `IMPLEMENTATIONS.md`: efecto convoy en FCFS, inanición posible en SJF/Prioridad, compromiso de quantum en RR.

Pruebas primero: invariantes (retorno = espera + ráfaga; Σ ráfagas = tiempo ocupado de CPU; respuesta ≤ espera) y coincidencia con la tabla de la Fase 4.

**Log de la fase:**

```text
Comparación | escenario=lote_pequeno.csv
 algoritmo  espera  retorno  respuesta  cpu%   cambios_ctx
 FCFS       5.25    9.50     5.25       100.0  3
 SJF        3.75    8.00     3.75       100.0  3
 PRIORIDAD  4.00    8.25     4.00       100.0  3
 RR(q=2)    7.00    ...      ...        ...    9
Mejor espera media: SJF
```

**Aceptación:** los números del log coinciden con la tabla de oráculo; CSV, JSON y PNG generados en `resultados/`.

### Fase 7: Integración con el orquestador y CLI

- [ ] Adaptador `ejecutar(config) -> ModuleResult` para el módulo (cumple `core/contratos.py`).
- [ ] `main.py procesos --escenario ... --algoritmo FCFS|SJF|RR|PRIORIDAD|todos --quantum N --verbose`.
- [ ] `make procesos` (Python) y `make procesos-c` (demos C) en el `Makefile` raíz; `make test` ejecuta `pytest` y las comprobaciones de C.
- [ ] Un fallo recuperable (escenario con una fila inválida) queda en `ModuleResult.errores`; nunca termina en silencio.
- [ ] Verificar que el módulo no importa a `modulo2`..`modulo7` (prueba de dependencias).

Pruebas primero: integración con `lote_pequeno.csv`, `lote_grande.csv` y un CSV corrupto.

**Log de la fase:** una ejecución completa que encadena demos y planificación.

```text
$ python main.py procesos --algoritmo todos --escenario escenarios/lote_pequeno.csv
[modulo1] estado=completado procesos=4 algoritmos=4 errores=0
```

**Aceptación:** `make test` verde de extremo a extremo; el resultado pasa por el contrato común.

### Fase 8: Robustez, calidad y cierre de documentación

- [ ] Escenarios límite: 1 proceso, 100 procesos generados, ráfagas muy desiguales (convoy), llegadas idénticas.
- [ ] C: `-fsanitize=address,undefined` y `valgrind` sin reportes; `-Werror` en CI local.
- [ ] Mejora opcional: Prioridad expropiativa y **aging** para demostrar inanición y su mitigación.
- [ ] Pruebas de regresión por cada bug hallado.
- [ ] `docs/IMPLEMENTATIONS.md` del módulo (mismo formato que Módulos 2 y 4): qué se hizo, comandos, resultados.
- [ ] Actualizar `README.md`, `docs/instalacion_y_ejecucion.md` y el estado de esqueletos.
- [ ] Preparar el material de sustentación: diagrama de estados, Gantt de los 4 algoritmos, tabla comparativa.

**Log de la fase:** reporte final de `make test` con conteo de pruebas y resultado de los sanitizers.

**Aceptación:** cobertura de las ramas de los 4 algoritmos; 0 warnings; documentación coherente con el código.

## 6. Orden, dependencias y paralelización

```text
Fase 0 ──► Fase 1 ──► Fase 4 ──► Fase 5 ──► Fase 6 ──► Fase 7 ──► Fase 8
   │                                                        ▲
   ├──► Fase 2 (C, independiente) ──────────────────────────┤
   └──► Fase 3 (C, independiente) ──────────────────────────┘
```

- **Camino crítico:** 0 → 1 → 4 → 5 → 6 → 7.
- **Paralelizable** una vez cerrada la Fase 0: las Fases 2 y 3 (C) no comparten archivos con el camino Python; pueden hacerse en hilos/agentes separados (`ct thread create ... --worktree`). Las Fases 4 y 5 comparten `planificador.py`: se hacen en secuencia o se fija antes la firma común.
- **Prioridad para el parcial (semana 8):** Fases 0, 1, 4, 5, 6 y la demo de la Fase 2. Las Fases 3, 7 y 8 se terminan sin bloquear la entrega.

## 7. Definición de terminado (módulo completo)

- [ ] Los 4 algoritmos producen las métricas del oráculo y su Gantt.
- [ ] Demos C compilan sin warnings y su log muestra PIDs/TIDs reales.
- [ ] Cada fase tiene su log verificable en consola.
- [ ] `make test` verde; sanitizers limpios.
- [ ] `core/` consumido también por los Módulos 3 y 4.
- [ ] Commits pequeños por fase con mensaje claro (criterio de la rúbrica "control de versiones").

## 8. Riesgos y preguntas abiertas

| Riesgo / duda | Mitigación |
| --- | --- |
| Los Módulos 3 y 4 ya definieron sus propios `Evento`/`Resultado` | Fase 0 reutiliza sus campos (`instante, modulo, entidad, accion, datos`) para minimizar la migración |
| Convención de prioridad no definida en el enunciado | Decidida aquí (menor = más prioritaria); confirmar con el docente |
| Paquetes con carpeta `py/` hacen que el import sea `modulo1_procesos.py.cli` | Se mantiene por compatibilidad con el Módulo 4; no renombrar sin acuerdo del equipo |
| Las pruebas de C dependen de `gcc` y de Linux/WSL | Marcar con `pytest.mark.skipif` si no hay compilador |
| Rama de Módulo 3 sin fusionar | Coordinar con Gabriel; la Fase 0 no depende de ella |
