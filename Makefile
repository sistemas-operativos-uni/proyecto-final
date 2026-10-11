PYTHON ?= python3

.PHONY: help install test cargar clean

help:
	@echo "install  Instala las dependencias Python"
	@echo "test     Ejecuta las pruebas disponibles"
	@echo "cargar   Valida y muestra escenarios/lote_pequeno.csv (ESCENARIO=ruta para otro)"
	@echo "clean    Elimina objetos y cachés generados"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

# Log de la Fase 0: carga el escenario con core/ y muestra la tabla.
ESCENARIO ?= escenarios/lote_pequeno.csv
cargar:
	$(PYTHON) main.py cargar --escenario $(ESCENARIO)

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.o' -o -name '*.obj' \) -delete
