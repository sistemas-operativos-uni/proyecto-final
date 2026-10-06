CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -pthread

.PHONY: help check clean

help:
	@echo "Fuentes iniciales: lectores_escritores.c y semaforos.c"
	@echo "Los esqueletos comentados aún no generan ejecutables."

check:
	$(CC) --version

clean:
	rm -f *.o lectores_escritores semaforos lectores_escritores.exe semaforos.exe
