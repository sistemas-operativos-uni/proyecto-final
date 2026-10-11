"""AddressSanitizer, UndefinedBehaviorSanitizer y Valgrind sobre los programas en C.

`make sanitize` compila crear_proceso y hilos con `-fsanitize=address,undefined`.
Un sanitizer limpio solo significa algo si se sabe que detecta errores en este
equipo. Por eso cada comprobación va con un control negativo: un programa roto
a propósito que el sanitizer debe reportar.

ThreadSanitizer no se combina con AddressSanitizer en el mismo binario; sus
pruebas están en tests/test_hilos_c.py.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

DIR_C = Path(__file__).resolve().parent.parent / "modulo1_procesos" / "c"
BINARIOS = {"crear_proceso": DIR_C / "crear_proceso_asan", "hilos": DIR_C / "hilos_asan"}
FLAGS = ["-std=c11", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-g", "-O1"]

pytestmark = pytest.mark.skipif(
    shutil.which("gcc") is None or shutil.which("make") is None,
    reason="se necesitan gcc y make",
)

# Texto que los sanitizers escriben cuando encuentran algo.
MARCAS = ("AddressSanitizer", "LeakSanitizer", "runtime error", "UndefinedBehaviorSanitizer")


def hay_reporte(texto):
    return any(marca in texto for marca in MARCAS)


def make(*objetivos):
    return subprocess.run(["make", *objetivos], cwd=DIR_C, capture_output=True, text=True, timeout=180)


def ejecutar(binario, *args):
    return subprocess.run([str(binario), *args], capture_output=True, text=True, timeout=60)


@pytest.fixture(scope="module")
def sanitizado():
    """Recompila con sanitizers. Se omite si este compilador no los soporta."""
    assert make("clean").returncode == 0
    resultado = make("sanitize")
    if resultado.returncode != 0 and "sanitize" in resultado.stderr and "cannot find" in resultado.stderr:
        pytest.skip(f"el compilador no soporta -fsanitize=address,undefined: {resultado.stderr[-200:]}")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    for binario in BINARIOS.values():
        assert binario.exists(), f"falta {binario.name}"
    return resultado


def compilar_defectuoso(tmp_path, nombre, codigo):
    fuente = tmp_path / f"{nombre}.c"
    fuente.write_text(codigo, encoding="utf-8")
    binario = tmp_path / nombre
    r = subprocess.run(["gcc", *FLAGS, "-o", str(binario), str(fuente)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return binario


# --- Compilación ------------------------------------------------------------


def test_make_sanitize_compila_ambos_programas_sin_advertencias(sanitizado):
    salida = sanitizado.stdout + sanitizado.stderr
    assert "warning" not in salida.lower()
    for bandera in ("-fsanitize=address,undefined", "-Wall", "-Wextra", "-Wpedantic"):
        assert bandera in sanitizado.stdout


def test_las_fallas_de_ub_son_fatales_y_no_solo_un_aviso(sanitizado):
    # Sin -fno-sanitize-recover, UBSan imprime el error y el programa sale con 0.
    assert "-fno-sanitize-recover=all" in sanitizado.stdout


# --- Controles negativos: los sanitizers detectan errores en este equipo ------


def test_control_asan_detecta_un_uso_despues_de_liberar(sanitizado, tmp_path):
    # Se eligió un use-after-free y no un desborde: en un desborde, UBSan
    # (comprobación object-size) salta antes que ASan y el reporte no es de ASan.
    binario = compilar_defectuoso(
        tmp_path,
        "uso_tras_liberar",
        "#include <stdlib.h>\nint main(void){volatile int *a = malloc(sizeof(int)); free((void *)a); *a = 1; return 0;}\n",
    )
    r = ejecutar(binario)
    assert r.returncode != 0 and "heap-use-after-free" in r.stderr


def test_control_los_desbordes_de_memoria_dinamica_no_pasan_desapercibidos(sanitizado, tmp_path):
    binario = compilar_defectuoso(
        tmp_path,
        "desborde",
        "#include <stdlib.h>\nint main(void){int *a = malloc(4 * sizeof(int)); a[4] = 1; free(a); return 0;}\n",
    )
    r = ejecutar(binario)
    assert r.returncode != 0 and hay_reporte(r.stderr)  # lo reporta ASan o UBSan, el que llegue primero


def test_control_lsan_detecta_una_fuga(sanitizado, tmp_path):
    binario = compilar_defectuoso(
        tmp_path,
        "fuga",
        "#include <stdlib.h>\nint main(void){void *volatile p = malloc(64); p = NULL; return 0;}\n",
    )
    r = ejecutar(binario)
    assert r.returncode != 0 and "LeakSanitizer" in r.stderr


def test_control_ubsan_detecta_un_desbordamiento_de_entero_con_signo(sanitizado, tmp_path):
    binario = compilar_defectuoso(
        tmp_path,
        "desborde_entero",
        "#include <limits.h>\nint main(int c, char **v){(void)v; int x = INT_MAX; x += c; return x == 0;}\n",
    )
    r = ejecutar(binario)
    assert r.returncode != 0 and "signed integer overflow" in r.stderr


# --- Los programas del módulo ------------------------------------------------


def test_crear_proceso_corre_limpio_bajo_asan_y_ubsan(sanitizado):
    r = ejecutar(BINARIOS["crear_proceso"])
    assert r.returncode == 0, r.stderr
    assert not hay_reporte(r.stderr), r.stderr
    assert "6/6 hijos recogidos, 0 zombies" in r.stdout


def test_crear_proceso_con_otro_numero_de_solicitudes_corre_limpio(sanitizado):
    for n in ("1", "16"):
        r = ejecutar(BINARIOS["crear_proceso"], n)
        assert r.returncode == 0 and not hay_reporte(r.stderr), (n, r.stderr)


def test_hilos_corre_limpio_bajo_asan_y_ubsan(sanitizado):
    r = ejecutar(BINARIOS["hilos"])
    assert r.returncode == 0, r.stderr
    assert not hay_reporte(r.stderr), r.stderr
    assert "join OK; total=7 (esperado=7)" in r.stdout


def test_hilos_demo_carrera_corre_limpio_bajo_asan_y_ubsan(sanitizado):
    # ASan no ve carreras de datos (eso lo hace TSan), pero sí vería un
    # desborde o un entero mal sumado dentro del contador.
    r = ejecutar(BINARIOS["hilos"], "--demo-carrera")
    assert r.returncode == 0, r.stderr
    assert not hay_reporte(r.stderr), r.stderr
    assert "con mutex: contador=3000000 esperado=3000000" in r.stdout


def test_hilos_repetido_veinte_veces_no_reporta_nada(sanitizado):
    for corrida in range(20):
        r = ejecutar(BINARIOS["hilos"])
        assert r.returncode == 0 and not hay_reporte(r.stderr), (corrida, r.stderr)


@pytest.mark.parametrize("programa, argumentos", [("crear_proceso", ["0"]), ("crear_proceso", ["abc"]), ("hilos", ["--x"])])
def test_los_caminos_de_error_de_uso_tambien_corren_limpios(sanitizado, programa, argumentos):
    # El código de salida 2 pasa por rutas poco usadas: se comprueba que no tengan UB.
    r = ejecutar(BINARIOS[programa], *argumentos)
    assert r.returncode == 2 and not hay_reporte(r.stderr), r.stderr


def test_make_clean_borra_los_binarios_sanitizados(sanitizado):
    assert make("clean").returncode == 0
    assert not any(b.exists() for b in BINARIOS.values())
    make("sanitize")  # deja el árbol compilado para quien siga


# --- Valgrind ------------------------------------------------------------------

requiere_valgrind = pytest.mark.skipif(shutil.which("valgrind") is None, reason="valgrind no está instalado")


@pytest.fixture(scope="module")
def normales():
    """Binarios sin sanitizers: Valgrind no se lleva bien con ASan en el mismo binario."""
    assert make("clean").returncode == 0
    assert make("all").returncode == 0
    return DIR_C / "crear_proceso", DIR_C / "hilos"


def valgrind(binario, *args):
    return subprocess.run(
        ["valgrind", "--error-exitcode=99", "--leak-check=full", "--errors-for-leak-kinds=definite", str(binario), *args],
        capture_output=True,
        text=True,
        timeout=300,
    )


def resumenes_de_errores(stderr):
    """Cuántos errores reporta cada proceso observado: una cifra por línea ERROR SUMMARY."""
    return [int(n) for n in re.findall(r"ERROR SUMMARY: (\d+) errors", stderr)]


@requiere_valgrind
def test_valgrind_no_reporta_errores_ni_fugas_en_hilos(normales):
    r = valgrind(normales[1])
    assert r.returncode == 0, r.stderr
    assert resumenes_de_errores(r.stderr) == [0]
    # Con todo liberado Valgrind no imprime "definitely lost: 0 bytes"; imprime esta frase.
    assert "All heap blocks were freed -- no leaks are possible" in r.stderr


@requiere_valgrind
def test_valgrind_no_reporta_errores_ni_fugas_en_crear_proceso(normales):
    r = valgrind(normales[0], "2")
    assert r.returncode == 0, r.stderr
    # El código de salida de Valgrind solo describe al proceso padre. Los hijos
    # que siguen bajo Valgrind (hasta su exec) escriben su propio informe, y
    # uno con errores no cambiaría ese código: por eso se revisan todos.
    resumenes = resumenes_de_errores(r.stderr)
    assert len(resumenes) >= 2, r.stderr  # el padre y el hijo cuyo execvp falla
    assert set(resumenes) == {0}, r.stderr
    assert "definitely lost" not in r.stderr and "indirectly lost" not in r.stderr


@requiere_valgrind
def test_control_valgrind_detecta_una_lectura_de_memoria_sin_inicializar(tmp_path):
    fuente = tmp_path / "sin_inicializar.c"
    fuente.write_text("#include <stdio.h>\nint main(void){int x; if (x) puts(\"x\"); return 0;}\n", encoding="utf-8")
    binario = tmp_path / "sin_inicializar"
    assert subprocess.run(["gcc", "-O0", "-o", str(binario), str(fuente)]).returncode == 0
    r = valgrind(binario)
    assert r.returncode == 99 and "uninitialised" in r.stderr
