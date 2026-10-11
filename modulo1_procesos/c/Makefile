CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -pthread

# Las banderas de sanitizer van aparte: ralentizan el programa y solo sirven
# para comprobar carreras, no para la demostración normal.
TSAN_FLAGS ?= -fsanitize=thread -g -O1

.PHONY: help all check run-procesos run-hilos hilos-tsan clean

help:
	@echo "all           Compila crear_proceso y hilos"
	@echo "run-procesos  Ejecuta la demostración de fork/execvp/waitpid"
	@echo "run-hilos     Ejecuta la demostración de pthread_create/pthread_join"
	@echo "hilos-tsan    Compila hilos con ThreadSanitizer (hilos_tsan)"
	@echo "check         Muestra la versión del compilador"
	@echo "clean         Elimina binarios y objetos"

all: crear_proceso hilos

crear_proceso: crear_proceso.c
	$(CC) $(CFLAGS) -o $@ $<

hilos: hilos.c
	$(CC) $(CFLAGS) -o $@ $<

hilos-tsan: hilos.c
	$(CC) $(CFLAGS) $(TSAN_FLAGS) -o hilos_tsan $<

run-procesos: crear_proceso
	./crear_proceso

run-hilos: hilos
	./hilos

check:
	$(CC) --version

clean:
	rm -f *.o crear_proceso hilos hilos_tsan crear_proceso.exe hilos.exe
