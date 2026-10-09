/*
 * SO-Sim - Modulo 2: Sincronizacion de procesos
 * Archivo: modulo2_sincronizacion/c/lectores_escritores.c
 *
 * Lectores y escritores concurrentes sobre el padron compartido de matricula.
 *
 *   - Lector : consulta todos los cursos del padron (varios lectores a la vez).
 *   - Escritor: matricula (o retira) a un alumno en un curso; acceso exclusivo.
 *
 * Protocolo (tercer problema clasico de lectores-escritores, sin inanicion):
 *
 *   cola_servicio  (semaforo binario) : fila unica; todo lector o escritor pasa
 *                                       por ella, de modo que un escritor en
 *                                       espera no es rebasado por lectores
 *                                       que llegan despues.
 *   acceso_padron  (semaforo binario) : posesion del padron. El primer lector
 *                                       lo toma por todo el grupo; el ultimo
 *                                       lector lo libera. El escritor lo toma
 *                                       en exclusiva.
 *   mutex_lectores (pthread_mutex)    : protege el contador de lectores.
 *
 * Nota: POSIX no garantiza que sem_wait despierte en orden FIFO estricto; el
 * orden real de atencion queda registrado en la traza (inicio_seccion).
 *
 * Traza (stdout, CSV): instante,modulo,entidad,accion,datos
 *   instante = reloj logico (contador global, uno por evento)
 *   acciones = llegada | inicio_seccion | fin_seccion | violacion | resumen
 *   datos    = clave=valor separados por ';'
 *
 * Deteccion de errores: ademas del protocolo, el programa mide por separado
 * (con contadores atomicos) cuantos lectores y escritores estan dentro, y
 * valida que cada curso cumpla cupos + matriculados == CUPOS_POR_CURSO. Si algo
 * falla se emite un evento "violacion" y el codigo de salida es 1.
 *
 * Compilar:
 *   gcc -std=c11 -Wall -Wextra -pthread -O2 -o lectores_escritores lectores_escritores.c
 *
 * Uso:
 *   ./lectores_escritores                         (3 lectores, 2 escritores)
 *   ./lectores_escritores --lectores 5 --escritores 2
 *   ./lectores_escritores --orden LLELEEL         (orden de llegada explicito)
 *   ./lectores_escritores --escenario ops.csv     (id,tipo,llegada_ms,duracion_ms)
 *   ./lectores_escritores --orden LEEL --sin-sync (demuestra la corrupcion)
 *
 * Codigos de salida: 0 correcto, 1 violacion o padron danado, 2 uso invalido.
 */

#define _POSIX_C_SOURCE 200809L

#include <ctype.h>
#include <errno.h>
#include <pthread.h>
// #include <semaphore.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
    #include <string.h>
#include <time.h>

#define NUM_CURSOS 4
#define CUPOS_POR_CURSO 30
#define MAX_OPS 256
#define DURACION_MAX_MS 60000L
#define INTERVALO_DEFECTO_MS 2L
#define DURACION_DEFECTO_MS 10L

#if defined(__GNUC__)
#define FORMATO_PRINTF(a, b) __attribute__((format(printf, a, b)))
#else
#define FORMATO_PRINTF(a, b)
#endif

/* ------------------------------------------------------------------ */
/* Modelo de datos                                                     */
/* ------------------------------------------------------------------ */

typedef enum { OP_LECTOR, OP_ESCRITOR } tipo_op_t;

typedef struct {
    int id;
    tipo_op_t tipo;
    long llegada_ms;
    long duracion_ms;
    int indice; /* posicion original, para ordenar de forma estable */
} operacion_t;

/* volatile: evita que el compilador oculte lecturas/escrituras en el modo
 * --sin-sync; con sincronizacion correcta no es necesario. */
typedef struct {
    volatile int cupos[NUM_CURSOS];
    volatile int matriculados[NUM_CURSOS];
    volatile int version;
} padron_t;

static padron_t padron;
static operacion_t operaciones[MAX_OPS];
static int num_operaciones = 0;

/* Primitivas del protocolo */
static sem_t cola_servicio;
static sem_t acceso_padron;
static pthread_mutex_t mutex_lectores = PTHREAD_MUTEX_INITIALIZER;
static int lectores_en_recurso = 0; /* protegido por mutex_lectores */

/* Traza */
static pthread_mutex_t mutex_traza = PTHREAD_MUTEX_INITIALIZER;
static long secuencia = 0;

/* Instrumentacion independiente del protocolo */
static atomic_int lectores_activos = 0;
static atomic_int escritores_activos = 0;
static atomic_int max_lectores = 0;
static atomic_int violaciones = 0;
static atomic_int lecturas_ok = 0;
static atomic_int escrituras_ok = 0;

static bool usar_sync = true;
static struct timespec t_inicio;

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

/* Duerme hasta t_inicio + llegada_ms (reloj monotonico). */
static void esperar_llegada(long llegada_ms)
{
    struct timespec objetivo = t_inicio;

    objetivo.tv_sec += llegada_ms / 1000;
    objetivo.tv_nsec += (llegada_ms % 1000) * 1000000L;
    if (objetivo.tv_nsec >= 1000000000L) {
        objetivo.tv_sec += 1;
        objetivo.tv_nsec -= 1000000000L;
    }
    while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &objetivo, NULL) == EINTR) {
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

static void nombre_entidad(const operacion_t *op, char *destino, size_t tam)
{
    snprintf(destino, tam, "%c%d", op->tipo == OP_LECTOR ? 'L' : 'E', op->id);
}

static void registrar_violacion(const char *entidad, const char *motivo)
{
    atomic_fetch_add(&violaciones, 1);
    traza(entidad, "violacion", "motivo=%s", motivo);
}

/* ------------------------------------------------------------------ */
/* Protocolo de acceso al padron                                       */
/* ------------------------------------------------------------------ */

static void entrar_lector(void)
{
    if (!usar_sync) {
        return;
    }
    esperar_sem(&cola_servicio);
    bloquear(&mutex_lectores);
    if (lectores_en_recurso == 0) {
        esperar_sem(&acceso_padron); /* el primero toma el padron por el grupo */
    }
    lectores_en_recurso++;
    publicar_sem(&cola_servicio); /* el siguiente de la fila puede avanzar */
    desbloquear(&mutex_lectores);
}

static void salir_lector(void)
{
    if (!usar_sync) {
        return;
    }
    bloquear(&mutex_lectores);
    lectores_en_recurso--;
    if (lectores_en_recurso == 0) {
        publicar_sem(&acceso_padron); /* el ultimo lector libera el padron */
    }
    desbloquear(&mutex_lectores);
}

static void entrar_escritor(void)
{
    if (!usar_sync) {
        return;
    }
    esperar_sem(&cola_servicio);
    esperar_sem(&acceso_padron);
    publicar_sem(&cola_servicio);
}

static void salir_escritor(void)
{
    if (!usar_sync) {
        return;
    }
    publicar_sem(&acceso_padron);
}

/* ------------------------------------------------------------------ */
/* Hilos                                                               */
/* ------------------------------------------------------------------ */

static void leer_padron(const operacion_t *op, const char *entidad)
{
    long porcion = op->duracion_ms / NUM_CURSOS;
    int version_inicial = padron.version;

    for (int c = 0; c < NUM_CURSOS; c++) {
        int cupos = padron.cupos[c];
        dormir_ms(porcion); /* tiempo de consulta; un escritor sin exclusion corromperia esto */
        int matriculados = padron.matriculados[c];

        if (cupos + matriculados != CUPOS_POR_CURSO) {
            registrar_violacion(entidad, "padron_inconsistente");
        }
    }
    if (padron.version != version_inicial) {
        registrar_violacion(entidad, "escritura_durante_lectura");
    }
    atomic_fetch_add(&lecturas_ok, 1);
}

static void *hilo_lector(void *arg)
{
    const operacion_t *op = arg;
    char entidad[16];

    nombre_entidad(op, entidad, sizeof entidad);
    entrar_lector();

    int activos = atomic_fetch_add(&lectores_activos, 1) + 1;
    actualizar_maximo(&max_lectores, activos);
    if (atomic_load(&escritores_activos) != 0) {
        registrar_violacion(entidad, "lector_con_escritor_activo");
    }
    traza(entidad, "inicio_seccion", "lectores_activos=%d;version=%d", activos, padron.version);

    leer_padron(op, entidad);

    traza(entidad, "fin_seccion", "version=%d", padron.version);
    atomic_fetch_sub(&lectores_activos, 1);
    salir_lector();
    return NULL;
}

static void *hilo_escritor(void *arg)
{
    const operacion_t *op = arg;
    char entidad[16];

    nombre_entidad(op, entidad, sizeof entidad);
    entrar_escritor();

    int otros_escritores = atomic_fetch_add(&escritores_activos, 1);
    if (otros_escritores != 0) {
        registrar_violacion(entidad, "dos_escritores_activos");
    }
    if (atomic_load(&lectores_activos) != 0) {
        registrar_violacion(entidad, "escritor_con_lectores_activos");
    }

    int curso = op->id % NUM_CURSOS;
    int cupos = padron.cupos[curso];
    int delta = cupos > 0 ? -1 : +1; /* sin cupo: se libera una vacante (retiro) */
    traza(entidad, "inicio_seccion", "operacion=%s;curso=%d;version=%d",
          delta < 0 ? "matricula" : "retiro", curso, padron.version);

    /* Actualizacion en dos pasos: entre ambos el padron esta inconsistente.
     * Solo la exclusion mutua evita que un lector observe ese estado. */
    padron.cupos[curso] = cupos + delta;
    dormir_ms(op->duracion_ms);
    padron.matriculados[curso] = padron.matriculados[curso] - delta;
    padron.version = padron.version + 1;
    atomic_fetch_add(&escrituras_ok, 1);

    traza(entidad, "fin_seccion", "version=%d;curso=%d;cupos=%d", padron.version, curso,
          padron.cupos[curso]);
    atomic_fetch_sub(&escritores_activos, 1);
    salir_escritor();
    return NULL;
}

/* ------------------------------------------------------------------ */
/* Escenarios                                                          */
/* ------------------------------------------------------------------ */

static bool tipo_desde_caracter(char c, tipo_op_t *tipo)
{
    switch (toupper((unsigned char)c)) {
    case 'L': /* lector, lectura */
    case 'R': /* reader, read */
        *tipo = OP_LECTOR;
        return true;
    case 'E': /* escritor, escritura */
    case 'W': /* writer, write */
        *tipo = OP_ESCRITOR;
        return true;
    default:
        return false;
    }
}

static bool agregar_operacion(int id, tipo_op_t tipo, long llegada_ms, long duracion_ms)
{
    if (num_operaciones >= MAX_OPS) {
        fprintf(stderr, "Demasiadas operaciones (maximo %d)\n", MAX_OPS);
        return false;
    }
    if (id < 0 || llegada_ms < 0 || duracion_ms < 0 || duracion_ms > DURACION_MAX_MS) {
        fprintf(stderr, "Operacion %d con valores fuera de rango\n", id);
        return false;
    }
    for (int i = 0; i < num_operaciones; i++) {
        if (operaciones[i].id == id) {
            fprintf(stderr, "Identificador de operacion repetido: %d\n", id);
            return false;
        }
    }
    operaciones[num_operaciones] = (operacion_t){
        .id = id,
        .tipo = tipo,
        .llegada_ms = llegada_ms,
        .duracion_ms = duracion_ms,
        .indice = num_operaciones,
    };
    num_operaciones++;
    return true;
}

static bool cargar_orden(const char *orden, long intervalo_ms, long duracion_ms)
{
    for (size_t i = 0; orden[i] != '\0'; i++) {
        tipo_op_t tipo;

        if (!tipo_desde_caracter(orden[i], &tipo)) {
            fprintf(stderr, "Orden invalido: caracter '%c' (use L o E)\n", orden[i]);
            return false;
        }
        if (!agregar_operacion((int)i + 1, tipo, (long)i * intervalo_ms, duracion_ms)) {
            return false;
        }
    }
    if (num_operaciones == 0) {
        fprintf(stderr, "El orden de llegada esta vacio\n");
        return false;
    }
    return true;
}

/* Orden alternado: LELEL... hasta agotar lectores y escritores. */
static bool cargar_cantidades(int lectores, int escritores, long intervalo_ms, long duracion_ms)
{
    char orden[MAX_OPS + 1];
    int total = lectores + escritores;

    if (total <= 0 || total > MAX_OPS) {
        fprintf(stderr, "La cantidad total de hilos debe estar entre 1 y %d\n", MAX_OPS);
        return false;
    }
    for (int i = 0, l = lectores, e = escritores; i < total; i++) {
        bool toca_lector = (i % 2 == 0) ? (l > 0) : (e == 0);
        if (toca_lector) {
            orden[i] = 'L';
            l--;
        } else {
            orden[i] = 'E';
            e--;
        }
    }
    orden[total] = '\0';
    return cargar_orden(orden, intervalo_ms, duracion_ms);
}

/* CSV: id,tipo,llegada_ms[,duracion_ms]; encabezado y lineas '#' opcionales. */
static bool cargar_escenario(const char *ruta, long duracion_defecto_ms)
{
    FILE *archivo = fopen(ruta, "r");
    char linea[256];
    int numero_linea = 0;
    bool primera_fila = true;

    if (archivo == NULL) {
        fprintf(stderr, "No se pudo abrir %s: %s\n", ruta, strerror(errno));
        return false;
    }
    while (fgets(linea, sizeof linea, archivo) != NULL) {
        const char *p = linea;
        int id;
        char tipo_texto[32];
        long llegada_ms;
        long duracion_ms = duracion_defecto_ms;
        tipo_op_t tipo;

        numero_linea++;
        while (isspace((unsigned char)*p)) {
            p++;
        }
        if (*p == '\0' || *p == '#') {
            continue;
        }
        if (!isdigit((unsigned char)*p) && primera_fila) {
            primera_fila = false; /* encabezado */
            continue;
        }
        primera_fila = false;

        int leidos = sscanf(p, "%d , %31[^, \t\r\n] , %ld , %ld", &id, tipo_texto, &llegada_ms,
                            &duracion_ms);
        if (leidos < 3 || !tipo_desde_caracter(tipo_texto[0], &tipo)) {
            fprintf(stderr, "%s:%d: formato invalido (id,tipo,llegada_ms[,duracion_ms])\n", ruta,
                    numero_linea);
            fclose(archivo);
            return false;
        }
        if (!agregar_operacion(id, tipo, llegada_ms, duracion_ms)) {
            fprintf(stderr, "%s:%d: operacion rechazada\n", ruta, numero_linea);
            fclose(archivo);
            return false;
        }
    }
    fclose(archivo);
    if (num_operaciones == 0) {
        fprintf(stderr, "%s no contiene operaciones\n", ruta);
        return false;
    }
    return true;
}

static int comparar_llegada(const void *a, const void *b)
{
    const operacion_t *x = a;
    const operacion_t *y = b;

    if (x->llegada_ms != y->llegada_ms) {
        return x->llegada_ms < y->llegada_ms ? -1 : 1;
    }
    return x->indice - y->indice;
}

/* ------------------------------------------------------------------ */
/* Resultado                                                           */
/* ------------------------------------------------------------------ */

static bool padron_integro(int escrituras)
{
    for (int c = 0; c < NUM_CURSOS; c++) {
        if (padron.cupos[c] < 0 || padron.matriculados[c] < 0 ||
            padron.cupos[c] + padron.matriculados[c] != CUPOS_POR_CURSO) {
            return false;
        }
    }
    return padron.version == escrituras;
}

static void describir_padron(char *destino, size_t tam)
{
    size_t usado = 0;

    destino[0] = '\0';
    for (int c = 0; c < NUM_CURSOS && usado < tam; c++) {
        int n = snprintf(destino + usado, tam - usado, "%s%d:%d/%d", c ? "|" : "", c,
                         padron.cupos[c], padron.matriculados[c]);
        if (n < 0) {
            break;
        }
        usado += (size_t)n;
    }
}

static void uso(const char *programa)
{
    fprintf(stderr,
            "Uso: %s [opciones]\n"
            "  --lectores N       cantidad de lectores (defecto 3)\n"
            "  --escritores N     cantidad de escritores (defecto 2)\n"
            "  --orden CADENA     orden de llegada, p. ej. LLELE (L lector, E escritor)\n"
            "  --escenario ARCH   CSV id,tipo,llegada_ms[,duracion_ms]\n"
            "  --intervalo-ms N   separacion entre llegadas generadas (defecto %ld)\n"
            "  --duracion-ms N    duracion de cada operacion generada (defecto %ld)\n"
            "  --sin-sync         desactiva la sincronizacion (solo demostracion)\n"
            "  --ayuda            muestra este mensaje\n",
            programa, INTERVALO_DEFECTO_MS, DURACION_DEFECTO_MS);
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

int main(int argc, char **argv)
{
    long lectores = 3;
    long escritores = 2;
    long intervalo_ms = INTERVALO_DEFECTO_MS;
    long duracion_ms = DURACION_DEFECTO_MS;
    bool cantidades_dadas = false;
    const char *orden = NULL;
    const char *escenario = NULL;

    for (int i = 1; i < argc; i++) {
        const char *opcion = argv[i];
        bool lleva_valor = strcmp(opcion, "--sin-sync") != 0 && strcmp(opcion, "--ayuda") != 0;

        if (strcmp(opcion, "--ayuda") == 0) {
            uso(argv[0]);
            return 0;
        }
        if (strcmp(opcion, "--sin-sync") == 0) {
            usar_sync = false;
            continue;
        }
        if (!lleva_valor || i + 1 >= argc) {
            fprintf(stderr, "Opcion desconocida o sin valor: %s\n", opcion);
            uso(argv[0]);
            return 2;
        }
        const char *valor = argv[++i];
        bool ok = true;

        if (strcmp(opcion, "--lectores") == 0) {
            ok = leer_entero(valor, 0, MAX_OPS, &lectores);
            cantidades_dadas = true;
        } else if (strcmp(opcion, "--escritores") == 0) {
            ok = leer_entero(valor, 0, MAX_OPS, &escritores);
            cantidades_dadas = true;
        } else if (strcmp(opcion, "--intervalo-ms") == 0) {
            ok = leer_entero(valor, 0, DURACION_MAX_MS, &intervalo_ms);
        } else if (strcmp(opcion, "--duracion-ms") == 0) {
            ok = leer_entero(valor, 0, DURACION_MAX_MS, &duracion_ms);
        } else if (strcmp(opcion, "--orden") == 0) {
            orden = valor;
        } else if (strcmp(opcion, "--escenario") == 0) {
            escenario = valor;
        } else {
            fprintf(stderr, "Opcion desconocida: %s\n", opcion);
            uso(argv[0]);
            return 2;
        }
        if (!ok) {
            fprintf(stderr, "Valor invalido para %s: %s\n", opcion, valor);
            return 2;
        }
    }

    if ((orden != NULL) + (escenario != NULL) + cantidades_dadas > 1) {
        fprintf(stderr, "Use solo una fuente: --orden, --escenario o --lectores/--escritores\n");
        return 2;
    }
    bool cargado;
    if (orden != NULL) {
        cargado = cargar_orden(orden, intervalo_ms, duracion_ms);
    } else if (escenario != NULL) {
        cargado = cargar_escenario(escenario, duracion_ms);
    } else {
        cargado = cargar_cantidades((int)lectores, (int)escritores, intervalo_ms, duracion_ms);
    }
    if (!cargado) {
        return 2;
    }
    qsort(operaciones, (size_t)num_operaciones, sizeof operaciones[0], comparar_llegada);

    for (int c = 0; c < NUM_CURSOS; c++) {
        padron.cupos[c] = CUPOS_POR_CURSO;
        padron.matriculados[c] = 0;
    }
    if (sem_init(&cola_servicio, 0, 1) == -1 || sem_init(&acceso_padron, 0, 1) == -1) {
        fatal("sem_init");
    }

    puts("instante,modulo,entidad,accion,datos");
    clock_gettime(CLOCK_MONOTONIC, &t_inicio);

    pthread_t hilos[MAX_OPS];
    for (int i = 0; i < num_operaciones; i++) {
        operacion_t *op = &operaciones[i];
        char entidad[16];

        esperar_llegada(op->llegada_ms);
        nombre_entidad(op, entidad, sizeof entidad);
        traza(entidad, "llegada", "tipo=%s;llegada_ms=%ld;duracion_ms=%ld",
              op->tipo == OP_LECTOR ? "lector" : "escritor", op->llegada_ms, op->duracion_ms);
        if (pthread_create(&hilos[i], NULL, op->tipo == OP_LECTOR ? hilo_lector : hilo_escritor,
                           op) != 0) {
            fatal("pthread_create");
        }
    }
    for (int i = 0; i < num_operaciones; i++) {
        pthread_join(hilos[i], NULL);
    }

    int escrituras = atomic_load(&escrituras_ok);
    int lecturas = atomic_load(&lecturas_ok);
    int total_violaciones = atomic_load(&violaciones);
    bool integro = padron_integro(escrituras);
    char descripcion[128];

    describir_padron(descripcion, sizeof descripcion);
    traza("sistema", "resumen",
          "politica=%s;operaciones=%d;lecturas=%d;escrituras=%d;max_lectores=%d;"
          "violaciones=%d;integridad=%s;version=%d;padron=%s",
          usar_sync ? "cola_servicio" : "sin_sincronizacion", num_operaciones, lecturas,
          escrituras, atomic_load(&max_lectores), total_violaciones, integro ? "ok" : "danada",
          padron.version, descripcion);

    sem_destroy(&cola_servicio);
    sem_destroy(&acceso_padron);
    return (total_violaciones == 0 && integro) ? 0 : 1;
}