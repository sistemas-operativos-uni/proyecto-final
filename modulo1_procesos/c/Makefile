CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -pthread

# Las banderas de sanitizer van aparte: ralentizan el programa y solo sirven
# para comprobar carreras, no para la demostración normal.
TSAN_FLAGS ?= -fsanitize=thread -g -O1

# AddressSanitizer detecta desbordes y fugas de memoria; UndefinedBehaviorSanitizer,
# comportamiento indefinido (enteros que desbordan, punteros nulos). ThreadSanitizer
# no se combina con ASan en un mismo binario, por eso va en su propio objetivo.
# `-fno-sanitize-recover=all` hace fatal cada hallazgo: por defecto UBSan imprime
# el error y deja que el programa termine con código 0, y un CI no lo vería.
SAN_FLAGS ?= -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -g -O1

# `werror` convierte cada advertencia en un error para que ninguna pase
# desapercibida. Compila a /dev/null: comprueba y no deja archivos. Las fuentes
# y la bandera son variables para poder probarlo con un archivo defectuoso
# (FUENTES_C=otro.c) y apagarlo (WERROR=) y ver que la falla la causa -Werror.
FUENTES_C ?= crear_proceso.c hilos.c
WERROR ?= -Werror

.PHONY: help all check run-procesos run-hilos hilos-tsan sanitize werror clean

help:
	@echo "all           Compila crear_proceso y hilos"
	@echo "run-procesos  Ejecuta la demostración de fork/execvp/waitpid"
	@echo "run-hilos     Ejecuta la demostración de pthread_create/pthread_join"
	@echo "hilos-tsan    Compila hilos con ThreadSanitizer (hilos_tsan)"
	@echo "sanitize      Compila ambos programas con ASan y UBSan (*_asan)"
	@echo "werror        Comprueba que las fuentes compilan sin advertencias (-Werror)"
	@echo "check         Muestra la versión del compilador"
	@echo "clean         Elimina binarios y objetos"

all: crear_proceso hilos

crear_proceso: crear_proceso.c
	$(CC) $(CFLAGS) -o $@ $<

hilos: hilos.c
	$(CC) $(CFLAGS) -o $@ $<

hilos-tsan: hilos.c
	$(CC) $(CFLAGS) $(TSAN_FLAGS) -o hilos_tsan $<

sanitize: crear_proceso_asan hilos_asan

crear_proceso_asan: crear_proceso.c
	$(CC) $(CFLAGS) $(SAN_FLAGS) -o $@ $<

hilos_asan: hilos.c
	$(CC) $(CFLAGS) $(SAN_FLAGS) -o $@ $<

# El bucle se detiene en la primera fuente que falla (`|| exit 1`): sin eso,
# una fuente mala seguida de una limpia terminaría con código 0.
werror:
	@for fuente in $(FUENTES_C); do \
		echo "$(CC) $(CFLAGS) $(WERROR) -c -o /dev/null $$fuente"; \
		$(CC) $(CFLAGS) $(WERROR) -c -o /dev/null $$fuente || exit 1; \
	done

run-procesos: crear_proceso
	./crear_proceso

run-hilos: hilos
	./hilos

check:
	$(CC) --version

clean:
	rm -f *.o crear_proceso hilos hilos_tsan crear_proceso_asan hilos_asan crear_proceso.exe hilos.exe
