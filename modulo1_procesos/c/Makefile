CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -pthread

# `all` solo compila lo que ya está implementado. hilos.c entra en la Fase 3:
# con -Wpedantic, un archivo C vacío produce una advertencia.
.PHONY: help all check run-procesos clean

help:
	@echo "all           Compila los programas implementados (crear_proceso)"
	@echo "run-procesos  Ejecuta la demostración de fork/execvp/waitpid"
	@echo "check         Muestra la versión del compilador"
	@echo "clean         Elimina binarios y objetos"
	@echo "hilos.c sigue como esqueleto (Fase 3)."

all: crear_proceso

crear_proceso: crear_proceso.c
	$(CC) $(CFLAGS) -o $@ $<

run-procesos: crear_proceso
	./crear_proceso

check:
	$(CC) --version

clean:
	rm -f *.o crear_proceso hilos crear_proceso.exe hilos.exe
