PYTHON ?= python3

.PHONY: help install test cargar planificacion clean

help:
	@echo "install       Instala las dependencias Python"
	@echo "test          Ejecuta las pruebas disponibles"
	@echo "cargar        Valida y muestra escenarios/lote_pequeno.csv (ESCENARIO=ruta para otro)"
	@echo "planificacion Gantt y métricas de FCFS, SJF, Prioridad y RR (ALGORITMO, ESCENARIO, QUANTUM, CAMBIO_CONTEXTO)"
	@echo "clean         Elimina objetos y cachés generados"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

# Log de la Fase 0: carga el escenario con core/ y muestra la tabla.
ESCENARIO ?= escenarios/lote_pequeno.csv
cargar:
	$(PYTHON) main.py cargar --escenario $(ESCENARIO)

# Log de la Fase 4. La Fase 7 lo reemplaza por `main.py procesos`.
ALGORITMO ?= todos
QUANTUM ?= 2
CAMBIO_CONTEXTO ?= 0
planificacion:
	$(PYTHON) -m modulo1_procesos.py.planificador --escenario $(ESCENARIO) --algoritmo $(ALGORITMO) \
		--quantum $(QUANTUM) --cambio-contexto $(CAMBIO_CONTEXTO)

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.o' -o -name '*.obj' \) -delete
