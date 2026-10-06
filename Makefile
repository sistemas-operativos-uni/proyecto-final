PYTHON ?= python3

.PHONY: help install test clean

help:
	@echo "install  Instala las dependencias Python"
	@echo "test     Ejecuta las pruebas disponibles"
	@echo "clean    Elimina objetos y cachés generados"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f \( -name '*.o' -o -name '*.obj' \) -delete
