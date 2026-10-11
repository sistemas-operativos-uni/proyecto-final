/* Demuestra creación, ejecución y espera de procesos POSIX.
 *
 * Contexto del simulador: el padre es el "servidor de matrícula" y cada hijo
 * atiende una solicitud. El programa corre dos escenarios y termina con un
 * resumen que comprueba que no quedó ningún proceso zombi:
 *
 *   1. N solicitudes: N hijos ejecutan `echo matricula Pxxx` y terminan con 0.
 *   2. Casos de fallo: un hijo sale con 3, un exec falla (127) y un hijo
 *      muere por SIGKILL que le envía el padre.
 *
 * Uso: crear_proceso [N]     (N entre 1 y 16, por defecto 3)
 * Códigos de salida: 0 todo recogido, 1 fallo en la ejecución, 2 uso incorrecto.
 */

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#define SOLICITUDES_MIN 1
#define SOLICITUDES_MAX 16
#define SOLICITUDES_POR_DEFECTO 3
#define MAX_ARGS 8
#define LONG_ETIQUETA 96
#define SALIDA_EXEC_FALLIDO 127 /* convención de las shells para "no se pudo ejecutar" */

typedef struct {
    pid_t pid;
    char etiqueta[LONG_ETIQUETA]; /* el comando, para que el log sea legible */
} Hijo;

/* Contadores de la simulación. Solo los toca el padre, así que no hay carrera. */
static int hijos_creados = 0;
static int hijos_recogidos = 0;
static int fallos = 0;

static void uso(void) {
    fprintf(stderr, "uso: crear_proceso [N]   (N = solicitudes de matrícula, %d a %d, por defecto %d)\n",
            SOLICITUDES_MIN, SOLICITUDES_MAX, SOLICITUDES_POR_DEFECTO);
}

static const char *nombre_senal(int senal) {
    switch (senal) {
    case SIGKILL: return "SIGKILL";
    case SIGTERM: return "SIGTERM";
    case SIGSEGV: return "SIGSEGV";
    case SIGABRT: return "SIGABRT";
    case SIGINT:  return "SIGINT";
    default:      return "SIG?";
    }
}

/* Une argv en una línea para el log: {"echo","matricula","P001"} -> "echo matricula P001". */
static void armar_etiqueta(char *destino, size_t tam, char *const argv[]) {
    destino[0] = '\0';
    for (size_t i = 0; argv[i] != NULL; i++) {
        size_t usado = strlen(destino);
        snprintf(destino + usado, tam - usado, "%s%s", i == 0 ? "" : " ", argv[i]);
    }
}

/* Espera a que el hijo ejecute su programa nuevo (o muera intentándolo).
 *
 * El hijo hereda el extremo de escritura de una tubería marcado FD_CLOEXEC:
 * el sistema lo cierra solo en el instante del exec. Cuando el padre lee EOF,
 * el exec ya ocurrió y el hijo ya imprimió su línea de log. Sin esto, un kill
 * enviado enseguida podría matar al hijo antes de que escriba nada. */
static void esperar_exec(int fd_lectura) {
    char basura;
    ssize_t n;
    do {
        n = read(fd_lectura, &basura, 1);
    } while (n > 0 || (n < 0 && errno == EINTR));
}

/* Crea un hijo que ejecuta argv. Devuelve su pid o -1 si fork falla. */
static pid_t lanzar(char *const argv[], char *etiqueta, size_t tam_etiqueta) {
    int tuberia[2];
    armar_etiqueta(etiqueta, tam_etiqueta, argv);

    if (pipe(tuberia) == -1) {
        perror("pipe");
        return -1;
    }
    if (fcntl(tuberia[1], F_SETFD, FD_CLOEXEC) == -1) {
        perror("fcntl");
        close(tuberia[0]);
        close(tuberia[1]);
        return -1;
    }

    /* fork duplica los búferes de stdio sin vaciar. Si quedara texto
     * pendiente, padre e hijo lo imprimirían los dos. */
    fflush(stdout);
    fflush(stderr);

    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        close(tuberia[0]);
        close(tuberia[1]);
        return -1;
    }

    if (pid == 0) {
        /* Hijo. El programa tiene un solo hilo, así que printf es válido aquí.
         * Sale con _exit: exit vaciaría de nuevo los búferes heredados del padre. */
        close(tuberia[0]);
        printf("[hijo  pid=%d ppid=%d] ejecutando: %s\n", (int)getpid(), (int)getppid(), etiqueta);
        fflush(stdout);
        execvp(argv[0], argv);
        /* Si execvp regresa, falló. El programa nuevo nunca arrancó. */
        fprintf(stderr, "[hijo  pid=%d] execvp '%s' falló: %s\n", (int)getpid(), argv[0], strerror(errno));
        _exit(SALIDA_EXEC_FALLIDO);
    }

    /* Padre: cierra su copia de escritura, o nunca vería el EOF. */
    close(tuberia[1]);
    esperar_exec(tuberia[0]);
    close(tuberia[0]);
    hijos_creados++;
    return pid;
}

/* Recoge al hijo con waitpid y traduce el estado. Sin esta llamada el hijo
 * terminado queda como zombi: ocupa una entrada en la tabla de procesos. */
static void recoger(const Hijo *hijo) {
    int estado;
    pid_t r;
    do {
        r = waitpid(hijo->pid, &estado, 0);
    } while (r == -1 && errno == EINTR);

    if (r == -1) {
        fprintf(stderr, "[padre] waitpid(%d) falló: %s\n", (int)hijo->pid, strerror(errno));
        fallos++;
        return;
    }
    hijos_recogidos++;

    /* Un hijo termina por exit o por señal, nunca por ambas. */
    if (WIFEXITED(estado)) {
        printf("[padre] hijo %d (%s) terminó con estado=%d\n", (int)hijo->pid, hijo->etiqueta, WEXITSTATUS(estado));
    } else if (WIFSIGNALED(estado)) {
        printf("[padre] hijo %d (%s) terminado por señal %d (%s)\n", (int)hijo->pid, hijo->etiqueta,
               WTERMSIG(estado), nombre_senal(WTERMSIG(estado)));
    } else {
        printf("[padre] hijo %d (%s) terminó en un estado inesperado\n", (int)hijo->pid, hijo->etiqueta);
        fallos++;
    }
    fflush(stdout);
}

/* Escenario 1: lanza las N solicitudes a la vez y las recoge después, para
 * que se vea concurrencia real entre hijos. */
static void escenario_solicitudes(int n) {
    Hijo hijos[SOLICITUDES_MAX];
    int lanzados = 0;

    for (int i = 1; i <= n; i++) {
        /* 16 bytes cubren cualquier int: gcc no puede probar que i <= 16. */
        char id[16];
        snprintf(id, sizeof id, "P%03d", i);
        char *argv[] = {"echo", "matricula", id, NULL};
        pid_t pid = lanzar(argv, hijos[lanzados].etiqueta, sizeof hijos[lanzados].etiqueta);
        if (pid == -1) {
            fallos++;
            continue;
        }
        hijos[lanzados++].pid = pid;
    }
    for (int i = 0; i < lanzados; i++) {
        recoger(&hijos[i]);
    }
}

/* Escenario 2: los tres desenlaces que no son "terminó con 0". Corren de uno
 * en uno para que el log salga en orden fijo. */
static void escenario_fallos(void) {
    Hijo hijo;

    printf("[padre] --- escenario 2: salida distinta de cero, exec fallido y señal ---\n");
    fflush(stdout);

    char *salida_tres[] = {"sh", "-c", "exit 3", NULL};
    hijo.pid = lanzar(salida_tres, hijo.etiqueta, sizeof hijo.etiqueta);
    if (hijo.pid == -1) fallos++; else recoger(&hijo);

    /* El programa no existe: execvp falla en el hijo y este sale con 127. */
    char *inexistente[] = {"comando-que-no-existe", NULL};
    hijo.pid = lanzar(inexistente, hijo.etiqueta, sizeof hijo.etiqueta);
    if (hijo.pid == -1) fallos++; else recoger(&hijo);

    /* `sleep 30` no terminaría solo en la demo: el padre lo mata. lanzar ya
     * garantiza que el exec ocurrió, así que la señal llega al programa nuevo. */
    char *dormilon[] = {"sleep", "30", NULL};
    hijo.pid = lanzar(dormilon, hijo.etiqueta, sizeof hijo.etiqueta);
    if (hijo.pid == -1) {
        fallos++;
    } else {
        printf("[padre] enviando SIGKILL al hijo %d\n", (int)hijo.pid);
        fflush(stdout);
        if (kill(hijo.pid, SIGKILL) == -1) {
            perror("kill");
            fallos++;
        }
        recoger(&hijo);
    }
}

/* Barrido final: waitpid(-1, WNOHANG) recoge cualquier hijo que siga
 * pendiente. Devuelve ECHILD cuando no queda ninguno, y eso es lo esperado.
 * Cada pid que el barrido recoge era un zombi que el padre no había visto. */
static int contar_zombies(void) {
    int zombies = 0;
    int estado;
    pid_t r;
    while ((r = waitpid(-1, &estado, WNOHANG)) > 0) {
        zombies++;
    }
    return zombies;
}

/* Interpreta N con validación estricta: "3x", "" y "-2" se rechazan. */
static int leer_solicitudes(const char *texto, int *destino) {
    char *fin;
    errno = 0;
    long valor = strtol(texto, &fin, 10);
    if (errno != 0 || texto[0] == '\0' || *fin != '\0' || valor < SOLICITUDES_MIN || valor > SOLICITUDES_MAX) {
        return -1;
    }
    *destino = (int)valor;
    return 0;
}

int main(int argc, char *argv[]) {
    int solicitudes = SOLICITUDES_POR_DEFECTO;

    if (argc > 2 || (argc == 2 && leer_solicitudes(argv[1], &solicitudes) == -1)) {
        uso();
        return 2;
    }

    /* Salida por líneas: cada printf llega entero a la tubería de pytest,
     * sin mezclarse con las líneas de los hijos que escriben a la vez. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    printf("[padre pid=%d] creando %d hijos de matrícula\n", (int)getpid(), solicitudes);
    escenario_solicitudes(solicitudes);
    escenario_fallos();

    int zombies = contar_zombies();
    printf("[padre] %d/%d hijos recogidos, %d zombies\n", hijos_recogidos, hijos_creados, zombies);
    fflush(stdout);

    int ok = fallos == 0 && zombies == 0 && hijos_recogidos == hijos_creados;
    return ok ? 0 : 1;
}
