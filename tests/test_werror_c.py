"""`make werror`: las fuentes en C compilan sin una sola advertencia.

El objetivo compila cada fuente con las banderas del proyecto más `-Werror`,
que convierte cada advertencia en un error. No deja binarios: solo comprueba.
Se puede apuntar a otras fuentes con `FUENTES_C=...`, lo que permite probar
con un archivo defectuoso que el objetivo de verdad falla.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

DIR_C = Path(__file__).resolve().parent.parent / "modulo1_procesos" / "c"

pytestmark = pytest.mark.skipif(
    shutil.which("gcc") is None or shutil.which("make") is None,
    reason="se necesitan gcc y make",
)

# Una variable sin usar: -Wall la marca como advertencia y -Werror como error.
CON_ADVERTENCIA = "int main(void) { int sin_usar; return 0; }\n"
LIMPIO = "int main(void) { return 0; }\n"


def make(*argumentos):
    return subprocess.run(["make", *argumentos], cwd=DIR_C, capture_output=True, text=True, timeout=120)


def archivos():
    return sorted(p.name for p in DIR_C.iterdir() if p.name != "__pycache__")


def fuente(tmp_path, nombre, codigo):
    ruta = tmp_path / nombre
    ruta.write_text(codigo, encoding="utf-8")
    return str(ruta)


# --- Las fuentes del módulo ---------------------------------------------------


def test_make_werror_compila_las_fuentes_del_modulo_sin_advertencias():
    r = make("werror")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "warning" not in (r.stdout + r.stderr).lower()


def test_make_werror_usa_las_banderas_del_proyecto_mas_werror_sobre_ambas_fuentes():
    r = make("werror")
    for bandera in ("-std=c11", "-Wall", "-Wextra", "-Wpedantic", "-pthread", "-Werror"):
        assert bandera in r.stdout
    assert "crear_proceso.c" in r.stdout and "hilos.c" in r.stdout


def test_make_werror_no_deja_archivos_ni_binarios():
    antes = archivos()
    assert make("werror").returncode == 0
    assert archivos() == antes


def test_make_help_menciona_werror():
    assert "werror" in make("help").stdout


# --- Controles negativos: -Werror falla de verdad -------------------------------


def test_control_un_archivo_con_advertencia_hace_fallar_el_objetivo(tmp_path):
    mala = fuente(tmp_path, "mala.c", CON_ADVERTENCIA)
    r = make("werror", f"FUENTES_C={mala}")
    assert r.returncode != 0
    assert "unused-variable" in r.stderr and "-Werror" in r.stdout


def test_control_la_misma_fuente_solo_advierte_sin_werror(tmp_path):
    # Demuestra que la falla anterior la causa -Werror y no un error de sintaxis.
    mala = fuente(tmp_path, "mala.c", CON_ADVERTENCIA)
    r = make("werror", f"FUENTES_C={mala}", "WERROR=")
    assert r.returncode == 0
    assert "warning" in r.stderr.lower()


def test_control_un_archivo_limpio_pasa(tmp_path):
    limpio = fuente(tmp_path, "limpio.c", LIMPIO)
    assert make("werror", f"FUENTES_C={limpio}").returncode == 0


def test_control_basta_una_fuente_mala_entre_varias(tmp_path):
    limpio = fuente(tmp_path, "limpio.c", LIMPIO)
    mala = fuente(tmp_path, "mala.c", CON_ADVERTENCIA)
    for orden in ((mala, limpio), (limpio, mala)):
        r = make("werror", f"FUENTES_C={' '.join(orden)}")
        assert r.returncode != 0, orden
        # Sin esta línea la prueba pasaría también si el objetivo no existiera.
        assert "unused-variable" in r.stderr, orden
