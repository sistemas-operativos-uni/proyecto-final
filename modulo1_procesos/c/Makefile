CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -pthread

.PHONY: help check clean

help:
	@echo "Fuentes iniciales: crear_proceso.c y hilos.c"
	@echo "Los esqueletos comentados aún no generan ejecutables."

check:
	$(CC) --version

clean:
	rm -f *.o crear_proceso hilos crear_proceso.exe hilos.exe
