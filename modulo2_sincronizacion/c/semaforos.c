/*
 * SO-Sim - Modulo 2: Sincronizacion de procesos
 * Archivo: modulo2_sincronizacion/c/semaforos.c
 *
 * Validadores concurrentes de matricula que incrementan un contador compartido
 * (alumnos matriculados en un curso). Compara cuatro formas de coordinarlos:
 *
 *   sin-sync : sin proteccion. Es la condicion de carrera: se pierden
 *              incrementos. Solo es demostracion; no se registra traza de las
 *              secciones para no alterar el comportamiento observado.
 *   mutex    : pthread_mutex; un validador a la vez.
 *   binario  : semaforo POSIX con valor inicial 1; un validador a la vez.
 *   contador : semaforo POSIX con valor inicial V (ventanillas): hasta V
 *              validadores dentro de la zona de atencion; la actualizacion del
 *              contador va protegida por un mutex interno.
 *   todos    : ejecuta los cuatro modos, uno tras otro.
 *
 * Traza (stdout, CSV): instante,modulo,entidad,accion,datos
 *   acciones = inicio_seccion | fin_seccion | violacion | resumen
 *   Se emite inicio_seccion DESPUES de entrar y fin_seccion ANTES de salir, de
 *   modo que los intervalos registrados quedan dentro de la seccion real.
 *
 * Compilar:
 *   gcc -std=c11 -Wall -Wextra -pthread -O2 -o semaforos semaforos.c
 *
 * Uso:
 *   ./semaforos --modo todos
 *   ./semaforos --modo contador --hilos 6 --ventanillas 2 --duracion-ms 5
 *   ./semaforos --modo sin-sync --hilos 8 --iteraciones 5000 --duracion-ms 0
 *
 * Codigos de salida: 0 correcto, 1 contador incorrecto o limite excedido
 * (nunca por perdidas en sin-sync, que es la demostracion), 2 uso invalido.
 */

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <semaphore.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_HILOS 64
#define MAX_ITERACIONES 100000L
#define DURACION_MAX_MS 10000L

#if defined(__GNUC__)
#define FORMATO_PRINTF(a, b) __attribute__((format(printf, a, b)))
#else
#define FORMATO_PRINTF(a, b)
#endif

typedef enum { MODO_SIN_SYNC, MODO_MUTEX, MODO_BINARIO, MODO_CONTADOR, MODO_TODOS } modo_t;

static const char *const NOMBRES_MODO[] = {"sin-sync", "mutex", "binario", "contador", "todos"};

typedef struct {
    int hilos;
    long iteraciones;
    int ventanillas;
    long duracion_ms;
} config_t;

static config_t cfg = {.hilos = 4, .iteraciones = 3, .ventanillas = 2, .duracion_ms = 0};

static modo_t modo_actual;
static int limite_zona; /* 0 = sin limite (sin-sync) */

static volatile long contador_matriculas;

static sem_t sem_binario;
static sem_t sem_ventanillas;
static pthread_mutex_t mutex_seccion = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t mutex_contador = PTHREAD_MUTEX_INITIALIZER;

static pthread_mutex_t mutex_traza = PTHREAD_MUTEX_INITIALIZER;
static long secuencia;

static atomic_int en_zona = 0;
static atomic_int max_en_zona = 0;
static atomic_int violaciones = 0;

/* ------------------------------------------------------------------ */
/* Utilidades                                                          */
/* ------------------------------------------------------------------ */

static _Noreturn void fatal(const char *mensaje)
{
    perror(mensaje);
    exit(EXIT_FAILURE);
}

FORMATO_PRINTF(3, 4)
static void traza(const char *entidad, const char *accion, const char *formato, ...)
{
    va_list args;

    pthread_mutex_lock(&mutex_traza);
    printf("%ld,sincronizacion,%s,%s,", ++secuencia, entidad, accion);
    va_start(args, formato);
    vprintf(formato, args);
    va_end(args);
    putchar('\n');
    fflush(stdout);
    pthread_mutex_unlock(&mutex_traza);
}

static void dormir_ms(long ms)
{
    if (ms <= 0) {
        return;
    }
    struct timespec ts = {.tv_sec = ms / 1000, .tv_nsec = (ms % 1000) * 1000000L};
    while (nanosleep(&ts, &ts) == -1 && errno == EINTR) {
    }
}

static void esperar_sem(sem_t *s)
{
    while (sem_wait(s) == -1) {
        if (errno != EINTR) {
            fatal("sem_wait");
        }
    }
}

static void publicar_sem(sem_t *s)
{
    if (sem_post(s) == -1) {
        fatal("sem_post");
    }
}

static void bloquear(pthread_mutex_t *m)
{
    if (pthread_mutex_lock(m) != 0) {
        fatal("pthread_mutex_lock");
    }
}

static void desbloquear(pthread_mutex_t *m)
{
    if (pthread_mutex_unlock(m) != 0) {
        fatal("pthread_mutex_unlock");
    }
}

static void actualizar_maximo(atomic_int *maximo, int valor)
{
    int actual = atomic_load_explicit(maximo, memory_order_relaxed);

    while (valor > actual &&
           !atomic_compare_exchange_weak_explicit(maximo, &actual, valor, memory_order_relaxed,
                                                  memory_order_relaxed)) {
    }
}

/* ------------------------------------------------------------------ */
/* Entrada y salida de la zona protegida                               */
/* ------------------------------------------------------------------ */

static void entrar_zona(void)
{
    switch (modo_actual) {
    case MODO_MUTEX:
        bloquear(&mutex_seccion);
        break;
    case MODO_BINARIO:
        esperar_sem(&sem_binario);
        break;
    case MODO_CONTADOR:
        esperar_sem(&sem_ventanillas);
        break;
    default:
        break;
    }
}

static void salir_zona(void)
{
    switch (modo_actual) {
    case MODO_MUTEX:
        desbloquear(&mutex_seccion);
        break;
    case MODO_BINARIO:
        publicar_sem(&sem_binario);
        break;
    case MODO_CONTADOR:
        publicar_sem(&sem_ventanillas);
        break;
    default:
        break;
    }
}

/* Lectura-modificacion-escritura con cesion de CPU en medio: sin proteccion,
 * otro validador puede leer el mismo valor y un incremento se pierde. */
static void incrementar_contador(void)
{
    bool proteger = (modo_actual == MODO_CONTADOR);

    if (proteger) {
        bloquear(&mutex_contador);
    }
    long leido = contador_matriculas;
    sched_yield();
    contador_matriculas = leido + 1;
    if (proteger) {
        desbloquear(&mutex_contador);
    }
}

static void *hilo_validador(void *arg)
{
    int id = *(const int *)arg;
    char entidad[16];
    bool con_traza = (modo_actual != MODO_SIN_SYNC);

    snprintf(entidad, sizeof entidad, "V%d", id);
    for (long i = 1; i <= cfg.iteraciones; i++) {
        entrar_zona();

        int dentro = atomic_fetch_add_explicit(&en_zona, 1, memory_order_relaxed) + 1;
        actualizar_maximo(&max_en_zona, dentro);
        if (limite_zona > 0 && dentro > limite_zona) {
            atomic_fetch_add(&violaciones, 1);
            traza(entidad, "violacion", "motivo=limite_excedido;en_zona=%d;limite=%d", dentro,
                  limite_zona);
        }
        if (con_traza) {
            traza(entidad, "inicio_seccion", "iteracion=%ld;en_zona=%d", i, dentro);
        }

        incrementar_contador();
        dormir_ms(cfg.duracion_ms);

        if (con_traza) {
            traza(entidad, "fin_seccion", "iteracion=%ld", i);
        }
        atomic_fetch_sub_explicit(&en_zona, 1, memory_order_relaxed);
        salir_zona();
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Ejecucion de un modo                                                */
/* ------------------------------------------------------------------ */

static int ejecutar_modo(modo_t modo)
{
    pthread_t hilos[MAX_HILOS];
    int ids[MAX_HILOS];

    modo_actual = modo;
    secuencia = 0;
    contador_matriculas = 0;
    atomic_store(&en_zona, 0);
    atomic_store(&max_en_zona, 0);
    atomic_store(&violaciones, 0);
    limite_zona = (modo == MODO_MUTEX || modo == MODO_BINARIO) ? 1
                  : (modo == MODO_CONTADOR)                    ? cfg.ventanillas
                                                               : 0;
    if (sem_init(&sem_binario, 0, 1) == -1 ||
        sem_init(&sem_ventanillas, 0, (unsigned)cfg.ventanillas) == -1) {
        fatal("sem_init");
    }

    for (int i = 0; i < cfg.hilos; i++) {
        ids[i] = i + 1;
        if (pthread_create(&hilos[i], NULL, hilo_validador, &ids[i]) != 0) {
            fatal("pthread_create");
        }
    }
    for (int i = 0; i < cfg.hilos; i++) {
        pthread_join(hilos[i], NULL);
    }

    long esperado = (long)cfg.hilos * cfg.iteraciones;
    long final = contador_matriculas;
    int total_violaciones = atomic_load(&violaciones);

    traza("sistema", "resumen",
          "modo=%s;hilos=%d;iteraciones=%ld;esperado=%ld;final=%ld;perdidas=%ld;"
          "max_en_zona=%d;limite=%d;violaciones=%d",
          NOMBRES_MODO[modo], cfg.hilos, cfg.iteraciones, esperado, final, esperado - final,
          atomic_load(&max_en_zona), limite_zona, total_violaciones);

    sem_destroy(&sem_binario);
    sem_destroy(&sem_ventanillas);

    if (modo == MODO_SIN_SYNC) {
        return 0; /* demostracion: perder incrementos es el resultado esperado */
    }
    return (final == esperado && total_violaciones == 0) ? 0 : 1;
}

/* ------------------------------------------------------------------ */
/* Argumentos                                                          */
/* ------------------------------------------------------------------ */

static void uso(const char *programa)
{
    fprintf(stderr,
            "Uso: %s [opciones]\n"
            "  --modo M           sin-sync | mutex | binario | contador | todos (defecto todos)\n"
            "  --hilos N          validadores concurrentes, 1..%d (defecto 4)\n"
            "  --iteraciones N    secciones por validador (defecto 3)\n"
            "  --ventanillas V    valor inicial del semaforo contador (defecto 2)\n"
            "  --duracion-ms N    tiempo dentro de la seccion (defecto 0)\n"
            "  --ayuda            muestra este mensaje\n",
            programa, MAX_HILOS);
}

static bool leer_entero(const char *texto, long minimo, long maximo, long *salida)
{
    char *fin = NULL;

    errno = 0;
    long valor = strtol(texto, &fin, 10);
    if (errno != 0 || fin == texto || *fin != '\0' || valor < minimo || valor > maximo) {
        return false;
    }
    *salida = valor;
    return true;
}

static bool leer_modo(const char *texto, modo_t *modo)
{
    for (int i = 0; i <= (int)MODO_TODOS; i++) {
        if (strcmp(texto, NOMBRES_MODO[i]) == 0) {
            *modo = (modo_t)i;
            return true;
        }
    }
    return false;
}

int main(int argc, char **argv)
{
    modo_t modo = MODO_TODOS;

    for (int i = 1; i < argc; i++) {
        const char *opcion = argv[i];
        long valor = 0;
        bool ok = true;

        if (strcmp(opcion, "--ayuda") == 0) {
            uso(argv[0]);
            return 0;
        }
        if (i + 1 >= argc) {
            fprintf(stderr, "Opcion sin valor: %s\n", opcion);
            uso(argv[0]);
            return 2;
        }
        const char *texto = argv[++i];

        if (strcmp(opcion, "--modo") == 0) {
            ok = leer_modo(texto, &modo);
        } else if (strcmp(opcion, "--hilos") == 0) {
            ok = leer_entero(texto, 1, MAX_HILOS, &valor);
            cfg.hilos = (int)valor;
        } else if (strcmp(opcion, "--iteraciones") == 0) {
            ok = leer_entero(texto, 1, MAX_ITERACIONES, &cfg.iteraciones);
        } else if (strcmp(opcion, "--ventanillas") == 0) {
            ok = leer_entero(texto, 1, MAX_HILOS, &valor);
            cfg.ventanillas = (int)valor;
        } else if (strcmp(opcion, "--duracion-ms") == 0) {
            ok = leer_entero(texto, 0, DURACION_MAX_MS, &cfg.duracion_ms);
        } else {
            fprintf(stderr, "Opcion desconocida: %s\n", opcion);
            uso(argv[0]);
            return 2;
        }
        if (!ok) {
            fprintf(stderr, "Valor invalido para %s: %s\n", opcion, texto);
            return 2;
        }
    }

    puts("instante,modulo,entidad,accion,datos");
    if (modo != MODO_TODOS) {
        return ejecutar_modo(modo);
    }

    int estado = 0;
    for (modo_t m = MODO_SIN_SYNC; m <= MODO_CONTADOR; m++) {
        if (ejecutar_modo(m) != 0) {
            estado = 1;
        }
    }
    return estado;
}