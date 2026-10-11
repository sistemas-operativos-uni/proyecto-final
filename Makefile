PYTHON ?= python3

.PHONY: help install test cargar procesos procesos-c planificacion comparacion clean

help:
	@echo "install       Instala las dependencias Python"
	@echo "test          Ejecuta las pruebas disponibles"
	@echo "cargar        Valida y muestra escenarios/lote_pequeno.csv (ESCENARIO=ruta para otro)"
	@echo "procesos       Módulo 1 con el contrato común: main.py procesos (ALGORITMO, ESCENARIO, QUANTUM, CAMBIO_CONTEXTO)"
	@echo "procesos-c     Demostraciones en C del Módulo 1 (fork/exec/wait e hilos)"
	@echo "planificacion Gantt y métricas de FCFS, SJF, Prioridad y RR (ALGORITMO, ESCENARIO, QUANTUM, CAMBIO_CONTEXTO)"
	@echo "comparacion   Igual que planificacion y guarda procesos_<escenario>.csv/.json/.png (RESULTADOS=carpeta)"
	@echo "clean         Elimina objetos y cachés generados"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

# Log de la Fase 0: carga el escenario con core/ y muestra la tabla.
ESCENARIO ?= escenarios/lote_pequeno.csv
cargar:
	$(PYTHON) main.py cargar --escenario $(ESCENARIO)

# Módulo 1 a través del adaptador y del contrato ModuleResult (Fase 7).
procesos:
	$(PYTHON) main.py procesos --escenario $(ESCENARIO) --algoritmo $(ALGORITMO) \
		--quantum $(QUANTUM) --cambio-contexto $(CAMBIO_CONTEXTO)

# Demostraciones POSIX del Módulo 1: procesos con fork/execvp/waitpid e hilos con pthread.
procesos-c:
	$(MAKE) -C modulo1_procesos/c all run-procesos run-hilos

# Informes por algoritmo con Gantt y log. Usa la CLI propia del módulo, que
# trabaja con los resultados completos; `procesos` usa el contrato común.
ALGORITMO ?= todos
QUANTUM ?= 2
CAMBIO_CONTEXTO ?= 0
planificacion:
	$(PYTHON) -m modulo1_procesos.py.cli --escenario $(ESCENARIO) --algoritmo $(ALGORITMO) \
		--quantum $(QUANTUM) --cambio-contexto $(CAMBIO_CONTEXTO)

# Compara los cuatro algoritmos y exporta la comparación a CSV, JSON y un gráfico PNG.
RESULTADOS ?= resultados
comparacion:
	$(PYTHON) -m modulo1_procesos.py.cli --escenario $(ESCENARIO) --algoritmo todos \
		--quantum $(QUANTUM) --cambio-contexto $(CAMBIO_CONTEXTO) --exportar --resultados $(RESULTADOS)

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.o' -o -name '*.obj' \) -delete
