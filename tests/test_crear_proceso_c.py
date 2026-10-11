"""Compila y ejecuta modulo1_procesos/c/crear_proceso (Fase 2 del Módulo 1).

El programa crea procesos reales con fork/execvp, los espera con waitpid y
escribe un log. Estas pruebas lo ejecutan como lo haría un usuario y leen
ese log; no hay mocks.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

DIR_C = Path(__file__).resolve().parent.parent / "modulo1_procesos" / "c"
BINARIO = DIR_C / "crear_proceso"

pytestmark = pytest.mark.skipif(
    shutil.which("gcc") is None or shutil.which("make") is None,
    reason="se necesitan gcc y make",
)

RE_PADRE = re.compile(r"^\[padre pid=(\d+)\] creando (\d+) hijos", re.M)
RE_HIJO = re.compile(r"^\[hijo  pid=(\d+) ppid=(\d+)\] ejecutando: (.+)$", re.M)
RE_TERMINO = re.compile(r"^\[padre\] hijo (\d+) .*terminó con estado=(\d+)$", re.M)
RE_SENAL = re.compile(r"^\[padre\] hijo (\d+) .*terminado por señal (\d+) \((\w+)\)$", re.M)
RE_RESUMEN = re.compile(r"^\[padre\] (\d+)/(\d+) hijos recogidos, (\d+) zombies$", re.M)

# Escenarios fijos del programa: N solicitudes con estado 0, un hijo que sale
# con 3, un exec que falla (127) y un hijo al que el padre mata con SIGKILL.
HIJOS_EXTRA = 3


def make(*objetivos):
    return subprocess.run(
        ["make", *objetivos], cwd=DIR_C, capture_output=True, text=True, timeout=60
    )


def ejecutar(*args):
    return subprocess.run(
        [str(BINARIO), *args], capture_output=True, text=True, timeout=20
    )


@pytest.fixture(scope="module")
def compilado():
    """Recompila desde cero y deja el binario listo para las demás pruebas."""
    assert make("clean").returncode == 0
    resultado = make("all")
    assert BINARIO.exists(), resultado.stdout + resultado.stderr
    return resultado


@pytest.fixture(scope="module")
def corrida(compilado):
    # Popen y no run: hace falta el PID del padre para compararlo con el log.
    proceso = subprocess.Popen(
        [str(BINARIO)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    salida, errores = proceso.communicate(timeout=20)
    return proceso.pid, proceso.returncode, salida, errores


# --- Compilación -----------------------------------------------------------


def test_compila_sin_advertencias_con_wall_wextra_wpedantic(compilado):
    assert compilado.returncode == 0, compilado.stderr
    assert "warning" not in (compilado.stdout + compilado.stderr).lower()
    comando = compilado.stdout
    for bandera in ("-Wall", "-Wextra", "-Wpedantic"):
        assert bandera in comando


# --- Ejecución -------------------------------------------------------------


def test_termina_con_codigo_cero(corrida):
    _, codigo, _, errores = corrida
    assert codigo == 0, errores


def test_el_log_del_padre_usa_su_pid_real(corrida):
    pid_real, _, salida, _ = corrida
    coincidencia = RE_PADRE.search(salida)
    assert coincidencia, salida
    assert int(coincidencia.group(1)) == pid_real


def test_cada_hijo_reporta_al_padre_como_ppid_y_tiene_pid_propio(corrida):
    pid_real, _, salida, _ = corrida
    hijos = RE_HIJO.findall(salida)
    assert len(hijos) == 3 + HIJOS_EXTRA
    pids = [int(pid) for pid, _, _ in hijos]
    assert len(set(pids)) == len(pids)
    assert pid_real not in pids
    assert all(int(ppid) == pid_real for _, ppid, _ in hijos)


def test_las_tres_solicitudes_de_matricula_ejecutan_echo(corrida):
    _, _, salida, _ = corrida
    for numero in (1, 2, 3):
        assert f"ejecutando: echo matricula P00{numero}" in salida
        # La salida del propio echo llega por el stdout compartido.
        assert re.search(rf"^matricula P00{numero}$", salida, re.M)


def test_estados_de_salida_de_los_hijos(corrida):
    _, _, salida, _ = corrida
    estados = sorted(int(e) for _, e in RE_TERMINO.findall(salida))
    assert estados == [0, 0, 0, 3, 127]


def test_hijo_muerto_por_señal_se_reporta_con_numero_y_nombre(corrida):
    _, _, salida, _ = corrida
    assert [(int(s), n) for _, s, n in RE_SENAL.findall(salida)] == [(9, "SIGKILL")]


def test_cada_hijo_tiene_exactamente_un_desenlace_en_el_log(corrida):
    _, _, salida, _ = corrida
    creados = sorted(int(pid) for pid, _, _ in RE_HIJO.findall(salida))
    desenlaces = sorted(
        [int(p) for p, _ in RE_TERMINO.findall(salida)]
        + [int(p) for p, _, _ in RE_SENAL.findall(salida)]
    )
    assert desenlaces == creados


def test_cero_zombies_y_todos_los_hijos_recogidos(corrida):
    _, _, salida, _ = corrida
    resumen = RE_RESUMEN.search(salida)
    assert resumen, salida
    recogidos, creados, zombies = map(int, resumen.groups())
    assert (recogidos, creados, zombies) == (6, 6, 0)
    # El resumen es lo último que imprime el padre.
    assert salida.rstrip().splitlines()[-1] == resumen.group(0)


def test_el_exec_fallido_deja_mensaje_en_stderr(corrida):
    _, _, _, errores = corrida
    assert "execvp" in errores and "falló" in errores


# --- Argumentos ------------------------------------------------------------


def test_el_numero_de_solicitudes_se_pasa_por_argumento(compilado):
    resultado = ejecutar("5")
    assert resultado.returncode == 0, resultado.stderr
    assert RE_PADRE.search(resultado.stdout).group(2) == "5"
    assert "8/8 hijos recogidos, 0 zombies" in resultado.stdout


@pytest.mark.parametrize("argumento", ["0", "-2", "abc", "17", "3x", ""])
def test_argumento_invalido_devuelve_dos_con_uso(compilado, argumento):
    resultado = ejecutar(argumento)
    assert resultado.returncode == 2
    assert "uso:" in resultado.stderr.lower()
    assert resultado.stdout == ""


def test_demasiados_argumentos_devuelve_dos(compilado):
    assert ejecutar("2", "3").returncode == 2


# --- Makefile --------------------------------------------------------------


def test_make_run_procesos_ejecuta_la_demo(compilado):
    resultado = make("-s", "run-procesos")
    assert resultado.returncode == 0, resultado.stderr
    assert "0 zombies" in resultado.stdout


def test_make_clean_borra_el_binario(compilado):
    assert BINARIO.exists()
    assert make("clean").returncode == 0
    assert not BINARIO.exists()
    make("all")  # deja el árbol compilado para quien siga
