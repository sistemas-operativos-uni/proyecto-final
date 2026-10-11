"""Pruebas del punto de entrada: subcomandos `cargar` y `procesos` (Fase 0)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import main as punto_de_entrada

RAIZ = Path(__file__).resolve().parent.parent
LOTE_PEQUENO = RAIZ / "escenarios" / "lote_pequeno.csv"
LOTE_GRANDE = RAIZ / "escenarios" / "lote_grande.csv"


# --- cargar ----------------------------------------------------------------


def test_cargar_sin_ruta_valida_lote_pequeno_y_devuelve_cero(capsys):
    codigo = punto_de_entrada.main(["cargar"])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "[core] escenario=lote_pequeno.csv procesos=4 validación=OK" in salida


def test_cargar_muestra_la_tabla_de_procesos(capsys):
    punto_de_entrada.main(["cargar"])
    lineas = capsys.readouterr().out.splitlines()
    cabecera = next(l for l in lineas if l.startswith("id"))
    assert cabecera.split() == ["id", "llegada", "rafaga", "prioridad", "memoria_kb", "cursos"]
    fila_p004 = next(l for l in lineas if l.startswith("P004"))
    assert fila_p004.split() == ["P004", "4", "2", "2", "64", "SO101;ARQ110"]


def test_cargar_acepta_otra_ruta_con_escenario(capsys):
    codigo = punto_de_entrada.main(["cargar", "--escenario", str(LOTE_GRANDE)])
    assert codigo == 0
    assert "escenario=lote_grande.csv procesos=10 validación=OK" in capsys.readouterr().out


def test_cargar_con_fila_invalida_devuelve_uno_y_no_dice_ok(tmp_path, capsys):
    csv_malo = tmp_path / "malo.csv"
    csv_malo.write_text(
        "id,llegada,rafaga,prioridad,memoria_kb,cursos\nP001,0,0,2,128,SO101\n",
        encoding="utf-8",
    )
    codigo = punto_de_entrada.main(["cargar", "--escenario", str(csv_malo)])
    capturado = capsys.readouterr()
    assert codigo == 1
    assert "línea 2" in capturado.err
    assert "validación=OK" not in capturado.out


def test_cargar_con_archivo_inexistente_devuelve_uno(tmp_path, capsys):
    codigo = punto_de_entrada.main(["cargar", "--escenario", str(tmp_path / "no_existe.csv")])
    capturado = capsys.readouterr()
    assert codigo == 1
    assert "no_existe.csv" in capturado.err
    assert capturado.out == ""


# --- procesos --------------------------------------------------------------


def test_procesos_devuelve_dos_con_aviso_en_stderr(capsys):
    codigo = punto_de_entrada.main(["procesos"])
    capturado = capsys.readouterr()
    assert codigo == 2
    assert "no implementado" in capturado.err
    assert capturado.out == ""


# --- uso incorrecto --------------------------------------------------------


@pytest.mark.parametrize("argv", [[], ["inexistente"], ["cargar", "--escenario"]])
def test_uso_incorrecto_devuelve_dos_sin_lanzar_excepcion(argv, capsys):
    assert punto_de_entrada.main(argv) == 2
    assert capsys.readouterr().err != ""


# --- ejecución como programa -----------------------------------------------


def test_main_py_funciona_desde_cualquier_directorio(tmp_path):
    # El escenario por defecto se resuelve junto a main.py, no junto al cwd.
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / "main.py"), "cargar"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "validación=OK" in resultado.stdout


@pytest.mark.skipif(shutil.which("make") is None, reason="make no está instalado")
def test_make_cargar_ejecuta_el_subcomando():
    resultado = subprocess.run(
        ["make", "-s", "cargar"], cwd=RAIZ, capture_output=True, text=True
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "validación=OK" in resultado.stdout
