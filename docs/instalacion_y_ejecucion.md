# Instalación y ejecución

## Plataforma

Usa Python 3.11 o superior para el entorno del simulador. Los componentes C dependen de POSIX, por lo que deben compilarse y ejecutarse en Linux o WSL. En Linux, instala GCC, GNU Make y el paquete de desarrollo de Python desde el gestor de paquetes de la distribución.

## Entorno Python

En PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Linux o WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` instala `matplotlib`, `cryptography` y `pytest`.

## Herramientas del sistema (Debian y Ubuntu)

Si prefieres no usar un entorno virtual, o este no se puede crear porque falta `python3-venv`, instala las herramientas con `apt`:

```bash
sudo apt install gcc make python3-pytest python3-matplotlib
sudo apt install valgrind        # opcional
```

| Herramienta | Para qué sirve | Si falta |
| --- | --- | --- |
| `gcc` y `make` | Compilar los programas en C del Módulo 1 | Se omiten las pruebas de C |
| `pytest` | Ejecutar la suite | No se puede ejecutar `make test` |
| `matplotlib` | Gráfico de barras de la comparación | La exportación avisa de que no pudo graficar; se conservan el CSV y el JSON |
| `valgrind` | Buscar errores y fugas de memoria en los programas en C | Se omiten sus pruebas |

## Comandos del Módulo 1

Todos se ejecutan desde la raíz del repositorio.

### Objetivos de `make`

| Comando | Qué hace |
| --- | --- |
| `make cargar` | Valida `escenarios/lote_pequeno.csv` y muestra la tabla de procesos. `ESCENARIO=ruta` elige otro |
| `make procesos` | Ejecuta el Módulo 1 por el contrato común (`main.py procesos`) |
| `make procesos-c` | Compila y ejecuta las demostraciones en C: procesos con `fork` y `execvp`, e hilos con `pthread` |
| `make planificacion` | Informe de cada algoritmo con su Gantt y la tabla comparativa |
| `make comparacion` | Igual que `planificacion`, y guarda `procesos_<escenario>.csv`, `.json` y `.png` en `resultados/` |
| `make test` | Ejecuta toda la suite |
| `make install` | Instala las dependencias de `requirements.txt` |
| `make clean` | Borra cachés y objetos |

Los objetivos `procesos`, `planificacion` y `comparacion` aceptan `ALGORITMO` (`FCFS`, `SJF`, `PRIORIDAD`, `RR` o `todos`), `ESCENARIO`, `QUANTUM` y `CAMBIO_CONTEXTO`. `comparacion` acepta además `RESULTADOS` para cambiar la carpeta de salida. Ejemplo:

```bash
make planificacion ALGORITMO=RR QUANTUM=3 CAMBIO_CONTEXTO=1
```

### Línea de comandos

```bash
python main.py cargar --escenario escenarios/lote_grande.csv
python main.py procesos --algoritmo SJF
python main.py procesos --exportar --resultados resultados
python -m modulo1_procesos.py.cli --algoritmo FCFS --verbose
```

`main.py procesos` muestra el resultado del contrato `ModuleResult`: estado, tabla comparativa y errores. `python -m modulo1_procesos.py.cli` muestra además el Gantt ASCII y, con `--verbose`, el log de cada evento.

Códigos de salida de `main.py`: 0 todo bien; 1 escenario inválido o resultado con errores, que se escriben por la salida de error; 2 uso incorrecto.

### Programas en C

Se compilan con `make -C modulo1_procesos/c <objetivo>`:

| Objetivo | Qué hace |
| --- | --- |
| `all` | Compila `crear_proceso` y `hilos` con `-Wall -Wextra -Wpedantic` |
| `run-procesos` | Ejecuta la demostración de procesos |
| `run-hilos` | Ejecuta la demostración de hilos |
| `sanitize` | Compila con AddressSanitizer y UndefinedBehaviorSanitizer (`crear_proceso_asan`, `hilos_asan`) |
| `hilos-tsan` | Compila `hilos` con ThreadSanitizer (`hilos_tsan`) |
| `werror` | Comprueba que las fuentes compilan sin advertencias, con `-Werror` |
| `clean` | Borra los binarios |

```bash
make -C modulo1_procesos/c sanitize
./modulo1_procesos/c/hilos_asan
./modulo1_procesos/c/hilos --demo-carrera
```

## Pruebas

```bash
make test
python3 -m pytest tests/test_planificacion.py
```

Las pruebas de otros módulos viven en el mismo directorio `tests/`. Un `pytest` global falla hoy por un error del Módulo 2 ajeno al Módulo 1; el detalle está en la sección de problemas conocidos del [README](../README.md).
