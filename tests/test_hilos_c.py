"""Compila y ejecuta modulo1_procesos/c/hilos (Fase 3 del Módulo 1).

El programa lanza un hilo POSIX por curso, cada uno procesa las solicitudes
de matrícula de su curso y devuelve su conteo por pthread_join. Las pruebas
lo ejecutan como programa real y cruzan el resultado con el escenario CSV.
"""

import csv
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DIR_C = RAIZ / "modulo1_procesos" / "c"
BINARIO = DIR_C / "hilos"
BINARIO_TSAN = DIR_C / "hilos_tsan"
ESCENARIO = RAIZ / "escenarios" / "lote_pequeno.csv"

pytestmark = pytest.mark.skipif(
    shutil.which("gcc") is None or shutil.which("make") is None,
    reason="se necesitan gcc y make",
)

CURSOS = {"SO101", "BD202", "ARQ110"}
RE_MAIN = re.compile(r"^\[main pid=(\d+)\] lanzando (\d+) hilos", re.M)
RE_HILO = re.compile(
    r"^\[hilo (\w+) pid=(\d+) tid=(\d+)\] procesó (\d+) solicitudes?: (.+)$", re.M
)
RE_TOTAL = re.compile(r"^\[main\] join OK; total=(\d+) \(esperado=(\d+)\)$", re.M)
RE_IDENTIDAD = re.compile(r"^\[main\] mismo pid=(\w+), tids distintos=(\w+)$", re.M)


def solicitudes_por_curso():
    """Solicitudes esperadas por curso, leídas del escenario real."""
    cuenta = Counter()
    with ESCENARIO.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            for curso in filter(None, (c.strip() for c in fila["cursos"].split(";"))):
                cuenta[curso] += 1
    return cuenta


def make(*objetivos):
    return subprocess.run(
        ["make", *objetivos], cwd=DIR_C, capture_output=True, text=True, timeout=120
    )


def ejecutar(binario, *args):
    return subprocess.run(
        [str(binario), *args], capture_output=True, text=True, timeout=30
    )


@pytest.fixture(scope="module")
def compilado():
    """Recompila desde cero con el objetivo `all` del Makefile."""
    assert make("clean").returncode == 0
    resultado = make("all")
    assert BINARIO.exists(), resultado.stdout + resultado.stderr
    return resultado


@pytest.fixture(scope="module")
def corrida(compilado):
    # Popen y no run: hace falta el PID real para compararlo con el log.
    proceso = subprocess.Popen(
        [str(BINARIO)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    salida, errores = proceso.communicate(timeout=30)
    return proceso.pid, proceso.returncode, salida, errores


# --- Compilación -----------------------------------------------------------


def test_make_all_compila_hilos_sin_advertencias(compilado):
    assert compilado.returncode == 0, compilado.stderr
    assert "warning" not in (compilado.stdout + compilado.stderr).lower()
    for bandera in ("-Wall", "-Wextra", "-Wpedantic", "-pthread"):
        assert bandera in compilado.stdout


# --- Ejecución normal ------------------------------------------------------


def test_termina_con_codigo_cero(corrida):
    _, codigo, _, errores = corrida
    assert codigo == 0, errores


def test_el_log_principal_usa_el_pid_real_y_anuncia_tres_hilos(corrida):
    pid_real, _, salida, _ = corrida
    principal = RE_MAIN.search(salida)
    assert principal, salida
    assert int(principal.group(1)) == pid_real
    assert principal.group(2) == "3"


def test_hay_un_hilo_por_curso(corrida):
    _, _, salida, _ = corrida
    cursos = [curso for curso, *_ in RE_HILO.findall(salida)]
    assert sorted(cursos) == sorted(CURSOS)


def test_cada_hilo_procesa_las_solicitudes_de_su_curso_segun_el_escenario(corrida):
    _, _, salida, _ = corrida
    esperadas = solicitudes_por_curso()
    assert set(esperadas) == CURSOS
    for curso, _, _, cantidad, procesos in RE_HILO.findall(salida):
        assert int(cantidad) == esperadas[curso], curso
        assert len(procesos.split()) == int(cantidad)


def test_total_obtenido_es_igual_al_esperado(corrida):
    _, _, salida, _ = corrida
    total = RE_TOTAL.search(salida)
    assert total, salida
    obtenido, esperado = map(int, total.groups())
    assert obtenido == esperado == sum(solicitudes_por_curso().values())
    assert salida.rstrip().splitlines()[-1] == total.group(0)


def test_los_hilos_comparten_pid_y_tienen_tid_propio(corrida):
    pid_real, _, salida, _ = corrida
    hilos = RE_HILO.findall(salida)
    assert all(int(pid) == pid_real for _, pid, _, _, _ in hilos)
    tids = [tid for _, _, tid, _, _ in hilos]
    assert len(set(tids)) == len(tids) == 3
    assert RE_IDENTIDAD.search(salida).groups() == ("sí", "sí")


def test_cien_ejecuciones_seguidas_dan_siempre_el_mismo_total(compilado):
    esperado = sum(solicitudes_por_curso().values())
    for corrida_n in range(100):
        resultado = ejecutar(BINARIO)
        assert resultado.returncode == 0, (corrida_n, resultado.stderr)
        total = RE_TOTAL.search(resultado.stdout)
        assert total and int(total.group(1)) == esperado, (corrida_n, resultado.stdout)
        assert len(RE_HILO.findall(resultado.stdout)) == 3, (corrida_n, resultado.stdout)


# --- Demostración de la condición de carrera -------------------------------


def test_demo_carrera_el_contador_con_mutex_es_exacto(compilado):
    resultado = ejecutar(BINARIO, "--demo-carrera")
    assert resultado.returncode == 0, resultado.stderr
    assert "con mutex: contador=3000000 esperado=3000000" in resultado.stdout
    # El valor del contador sin mutex cambia de una corrida a otra y a veces
    # acierta por azar, así que la prueba solo exige que la línea exista.
    assert re.search(r"^\[main\] sin mutex: contador=\d+ esperado=3000000", resultado.stdout, re.M)


# --- Argumentos ------------------------------------------------------------


@pytest.mark.parametrize("argumentos", [["--otra"], ["x"], ["--demo-carrera", "extra"], [""]])
def test_argumentos_invalidos_devuelven_dos_con_uso(compilado, argumentos):
    resultado = ejecutar(BINARIO, *argumentos)
    assert resultado.returncode == 2
    assert "uso:" in resultado.stderr.lower()
    assert resultado.stdout == ""


# --- Makefile --------------------------------------------------------------


def test_make_run_hilos_ejecuta_la_demo(compilado):
    resultado = make("-s", "run-hilos")
    assert resultado.returncode == 0, resultado.stderr
    assert "join OK" in resultado.stdout


# --- ThreadSanitizer -------------------------------------------------------


@pytest.fixture(scope="module")
def tsan(compilado):
    """Compila con -fsanitize=thread. Se omite si este compilador no puede."""
    resultado = make("hilos-tsan")
    if resultado.returncode != 0 or not BINARIO_TSAN.exists():
        pytest.skip(f"el compilador no soporta -fsanitize=thread: {resultado.stderr[-200:]}")
    prueba = ejecutar(BINARIO_TSAN)
    if "unexpected memory mapping" in prueba.stderr:
        pytest.skip("ThreadSanitizer no arranca con el ASLR de este kernel")
    return BINARIO_TSAN


def test_tsan_no_reporta_nada_en_la_version_protegida(tsan):
    resultado = ejecutar(tsan)
    assert resultado.returncode == 0, resultado.stderr
    assert "ThreadSanitizer" not in resultado.stderr
    assert RE_TOTAL.search(resultado.stdout)


def test_tsan_detecta_la_carrera_del_contador_sin_mutex(tsan):
    # Control negativo: si TSan no viera esta carrera deliberada, su silencio
    # en la prueba anterior no probaría nada.
    resultado = ejecutar(tsan, "--demo-carrera")
    assert "ThreadSanitizer: data race" in resultado.stderr
    assert resultado.returncode != 0
