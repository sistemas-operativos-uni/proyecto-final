/* Demuestra creación y unión de hilos POSIX para el caso de matrícula.
 *
 * Un hilo atiende cada curso (SO101, BD202, ARQ110). Los tres comparten el
 * pid del proceso pero tienen identificador de hilo propio, que es la
 * diferencia con los hijos de fork de crear_proceso.c. Cada hilo recorre el
 * lote de solicitudes, cuenta las de su curso y devuelve ese conteo a main
 * por pthread_join; ninguna variable global recibe escrituras de los hilos.
 *
 * Modo extra: --demo-carrera suma un contador compartido desde tres hilos,
 * primero sin protección y luego con mutex, para mostrar la pérdida de
 * incrementos. La sincronización formal es tema del Módulo 2.
 *
 * Uso: hilos [--demo-carrera]
 * Códigos de salida: 0 todo correcto, 1 fallo en la ejecución, 2 uso incorrecto.
 */

#define _POSIX_C_SOURCE 200809L

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

#define NUM_CURSOS 3
#define ITERACIONES 1000000
#define LONG_LISTA 128

typedef struct {
    const char *proceso;
    const char *curso;
} Solicitud;

/* Una fila por par (proceso, curso) de escenarios/lote_pequeno.csv, columna
 * `cursos`. Si el CSV cambia, esta tabla y las pruebas deben cambiar con él. */
static const Solicitud LOTE[] = {
    {"P001", "SO101"},  {"P001", "BD202"},  {"P002", "SO101"}, {"P003", "ARQ110"},
    {"P003", "BD202"},  {"P004", "SO101"},  {"P004", "ARQ110"},
};
static const int LOTE_N = (int)(sizeof LOTE / sizeof LOTE[0]);
static const char *const CURSOS[NUM_CURSOS] = {"SO101", "BD202", "ARQ110"};

/* Lo que un hilo devuelve a main. Cada hilo reserva el suyo, así que dos hilos
 * nunca escriben en la misma memoria. */
typedef struct {
    const char *curso;
    int procesadas;
    char procesos[LONG_LISTA];
    pid_t pid;
    pthread_t tid;
} Resultado;

static void uso(void) {
    fprintf(stderr, "uso: hilos [--demo-carrera]\n");
}

/* Cuerpo del hilo de un curso. El argumento es el nombre del curso. */
static void *atender_curso(void *argumento) {
    const char *curso = argumento;
    Resultado *r = calloc(1, sizeof *r);
    if (r == NULL) {
        return NULL; /* main lo detecta: join devuelve NULL */
    }
    r->curso = curso;
    r->pid = getpid();
    r->tid = pthread_self();

    for (int i = 0; i < LOTE_N; i++) {
        if (strcmp(LOTE[i].curso, curso) != 0) {
            continue;
        }
        size_t usado = strlen(r->procesos);
        snprintf(r->procesos + usado, sizeof r->procesos - usado, "%s%s", usado == 0 ? "" : " ", LOTE[i].proceso);
        r->procesadas++;
    }

    /* pthread_t es un entero en Linux, pero el estándar no lo garantiza.
     * Se imprime como unsigned long solo para que el log distinga hilos. */
    printf("[hilo %s pid=%d tid=%lu] procesó %d solicitudes: %s\n", curso, (int)r->pid,
           (unsigned long)r->tid, r->procesadas, r->procesos);
    return r;
}

/* Lanza un hilo por curso y los une a todos. Llena `resultados`; un hilo que
 * falló deja NULL en su posición. Devuelve 0 si todo salió bien. */
static int escenario_cursos(Resultado *resultados[NUM_CURSOS]) {
    pthread_t hilos[NUM_CURSOS];
    int creados = 0;
    int fallos = 0;

    for (int i = 0; i < NUM_CURSOS; i++) {
        resultados[i] = NULL;
    }
    for (int i = 0; i < NUM_CURSOS; i++) {
        /* pthread_create devuelve el código de error; no usa errno. */
        int rc = pthread_create(&hilos[i], NULL, atender_curso, (void *)CURSOS[i]);
        if (rc != 0) {
            fprintf(stderr, "pthread_create(%s) falló: %s\n", CURSOS[i], strerror(rc));
            fallos++;
            break;
        }
        creados++;
    }

    /* Se une a todos los hilos que sí arrancaron, incluso si uno falló:
     * un hilo sin join deja recursos reservados hasta que el proceso muere. */
    for (int i = 0; i < creados; i++) {
        void *retorno = NULL;
        int rc = pthread_join(hilos[i], &retorno);
        if (rc != 0) {
            fprintf(stderr, "pthread_join(%s) falló: %s\n", CURSOS[i], strerror(rc));
            fallos++;
            continue;
        }
        if (retorno == NULL) {
            fprintf(stderr, "el hilo de %s no pudo reservar memoria\n", CURSOS[i]);
            fallos++;
            continue;
        }
        resultados[i] = retorno;
    }
    return fallos == 0 && creados == NUM_CURSOS ? 0 : -1;
}

static int modo_cursos(void) {
    Resultado *resultados[NUM_CURSOS];

    printf("[main pid=%d] lanzando %d hilos (uno por curso)\n", (int)getpid(), NUM_CURSOS);
    int estado = escenario_cursos(resultados);

    int total = 0;
    int mismo_pid = 1;
    int tids_distintos = 1;
    for (int i = 0; i < NUM_CURSOS; i++) {
        if (resultados[i] == NULL) {
            continue;
        }
        total += resultados[i]->procesadas;
        if (resultados[i]->pid != getpid()) {
            mismo_pid = 0;
        }
        for (int j = i + 1; j < NUM_CURSOS; j++) {
            if (resultados[j] != NULL && pthread_equal(resultados[i]->tid, resultados[j]->tid)) {
                tids_distintos = 0;
            }
        }
    }

    /* Un hilo que falló dejó NULL: ese caso ya cuenta como error en `estado`. */
    printf("[main] mismo pid=%s, tids distintos=%s\n", mismo_pid ? "sí" : "no", tids_distintos ? "sí" : "no");
    if (estado != 0 || total != LOTE_N || !mismo_pid || !tids_distintos) {
        printf("[main] ERROR: total=%d (esperado=%d)\n", total, LOTE_N);
        estado = -1;
    } else {
        printf("[main] join OK; total=%d (esperado=%d)\n", total, LOTE_N);
    }

    for (int i = 0; i < NUM_CURSOS; i++) {
        free(resultados[i]);
    }
    return estado == 0 ? 0 : 1;
}

/* --- Demostración de la condición de carrera ------------------------------ */

/* `volatile` obliga al compilador a leer y escribir memoria en cada vuelta.
 * Sin él, -O2 puede reducir el bucle a una sola suma y ocultar la carrera.
 * El incremento sigue sin ser atómico: es una carrera de datos a propósito. */
static volatile long contador_libre = 0;

static long contador_protegido = 0;
static pthread_mutex_t cerrojo = PTHREAD_MUTEX_INITIALIZER;

static void *sumar_sin_mutex(void *argumento) {
    (void)argumento;
    for (int i = 0; i < ITERACIONES; i++) {
        contador_libre = contador_libre + 1; /* leer, sumar, escribir: otro hilo se cuela en medio */
    }
    return NULL;
}

static void *sumar_con_mutex(void *argumento) {
    (void)argumento;
    for (int i = 0; i < ITERACIONES; i++) {
        /* Un fallo al tomar un mutex normal indica un error de programación,
         * no una condición recuperable: se aborta en vez de seguir sin exclusión. */
        if (pthread_mutex_lock(&cerrojo) != 0) {
            abort();
        }
        contador_protegido++; /* sección crítica mínima: una sola operación */
        if (pthread_mutex_unlock(&cerrojo) != 0) {
            abort();
        }
    }
    return NULL;
}

static int correr_sumadores(void *(*cuerpo)(void *)) {
    pthread_t hilos[NUM_CURSOS];
    int creados = 0;
    int fallos = 0;

    for (int i = 0; i < NUM_CURSOS; i++) {
        int rc = pthread_create(&hilos[i], NULL, cuerpo, NULL);
        if (rc != 0) {
            fprintf(stderr, "pthread_create falló: %s\n", strerror(rc));
            fallos++;
            break;
        }
        creados++;
    }
    for (int i = 0; i < creados; i++) {
        int rc = pthread_join(hilos[i], NULL);
        if (rc != 0) {
            fprintf(stderr, "pthread_join falló: %s\n", strerror(rc));
            fallos++;
        }
    }
    return fallos == 0 && creados == NUM_CURSOS ? 0 : -1;
}

static int modo_carrera(void) {
    const long esperado = (long)NUM_CURSOS * ITERACIONES;

    printf("[main pid=%d] %d hilos suman %d veces cada uno\n", (int)getpid(), NUM_CURSOS, ITERACIONES);

    if (correr_sumadores(sumar_sin_mutex) != 0) {
        return 1;
    }
    /* El resultado sin mutex varía por corrida y a veces acierta por azar.
     * Por eso no decide el código de salida. */
    printf("[main] sin mutex: contador=%ld esperado=%ld\n", contador_libre, esperado);

    if (correr_sumadores(sumar_con_mutex) != 0) {
        return 1;
    }
    printf("[main] con mutex: contador=%ld esperado=%ld\n", contador_protegido, esperado);

    return contador_protegido == esperado ? 0 : 1;
}

int main(int argc, char *argv[]) {
    int carrera = 0;

    if (argc > 2) {
        uso();
        return 2;
    }
    if (argc == 2) {
        if (strcmp(argv[1], "--demo-carrera") != 0) {
            uso();
            return 2;
        }
        carrera = 1;
    }

    /* Salida por líneas: cada printf de un hilo llega entero, sin mezclarse
     * con la línea de otro hilo. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    return carrera ? modo_carrera() : modo_cursos();
}
