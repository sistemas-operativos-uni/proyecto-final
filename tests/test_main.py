"""Pruebas del punto de entrada: subcomandos `cargar` y `procesos` (Fase 0)."""

import importlib.util
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

ESTADO_COMPLETADO = "[modulo1] estado=completado procesos=4 algoritmos=4 errores=0"


def test_procesos_ejecuta_el_modulo_1_y_devuelve_cero(capsys):
    codigo = punto_de_entrada.main(["procesos"])
    capturado = capsys.readouterr()
    assert codigo == 0
    assert capturado.err == ""
    assert ESTADO_COMPLETADO in capturado.out
    assert "== Comparación | escenario=lote_pequeno.csv ==" in capturado.out
    assert "Mejor espera media: SJF" in capturado.out


def test_procesos_con_un_algoritmo_muestra_solo_ese(capsys):
    assert punto_de_entrada.main(["procesos", "--algoritmo", "sjf"]) == 0
    salida = capsys.readouterr().out
    assert "estado=completado procesos=4 algoritmos=1 errores=0" in salida
    assert "SJF" in salida and "FCFS" not in salida and "Mejor" not in salida


def test_procesos_acepta_otro_escenario(capsys):
    assert punto_de_entrada.main(["procesos", "--escenario", str(LOTE_GRANDE)]) == 0
    assert "procesos=10 algoritmos=4" in capsys.readouterr().out


def test_procesos_usa_el_quantum_y_el_coste_indicados(capsys):
    assert punto_de_entrada.main(["procesos", "--quantum", "3", "--cambio-contexto", "1"]) == 0
    salida = capsys.readouterr().out
    assert "RR(q=3)" in salida
    assert "85.00" in salida  # FCFS: 17 de 20 unidades útiles


@pytest.mark.parametrize("opciones", [["--quantum", "0"], ["--quantum", "abc"], ["--cambio-contexto", "-1"]])
def test_procesos_rechaza_numeros_invalidos_con_codigo_dos(opciones, capsys):
    assert punto_de_entrada.main(["procesos", *opciones]) == 2
    assert capsys.readouterr().err != ""


def test_procesos_con_algoritmo_desconocido_devuelve_dos_y_lista_los_validos(capsys):
    assert punto_de_entrada.main(["procesos", "--algoritmo", "XYZ"]) == 2
    assert "FCFS, SJF, PRIORIDAD, RR" in capsys.readouterr().err


@pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="falta matplotlib")
def test_procesos_exportar_escribe_csv_json_y_grafico(tmp_path, capsys):
    assert punto_de_entrada.main(["procesos", "--exportar", "--resultados", str(tmp_path)]) == 0
    salida = capsys.readouterr().out
    assert (tmp_path / "procesos_lote_pequeno.csv").is_file()
    assert (tmp_path / "procesos_lote_pequeno.json").is_file()
    assert (tmp_path / "procesos_lote_pequeno.png").is_file()
    assert "[modulo1] exportado:" in salida and "procesos_lote_pequeno.png" in salida


def test_procesos_sin_exportar_no_escribe_nada(tmp_path, capsys):
    punto_de_entrada.main(["procesos", "--resultados", str(tmp_path)])
    assert list(tmp_path.iterdir()) == []


def test_procesos_exportar_con_un_algoritmo_devuelve_dos(tmp_path, capsys):
    codigo = punto_de_entrada.main(["procesos", "--algoritmo", "FCFS", "--exportar", "--resultados", str(tmp_path)])
    assert codigo == 2 and "todos" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_procesos_con_escenario_inexistente_falla_en_voz_alta(tmp_path, capsys):
    codigo = punto_de_entrada.main(["procesos", "--escenario", str(tmp_path / "no_existe.csv")])
    capturado = capsys.readouterr()
    assert codigo == 1
    assert "estado=fallido procesos=0 algoritmos=0 errores=1" in capturado.out
    assert "[modulo1] error:" in capturado.err and "no_existe.csv" in capturado.err


def test_procesos_con_fila_invalida_muestra_resultados_y_el_error(tmp_path, capsys):
    csv_parcial = tmp_path / "parcial.csv"
    csv_parcial.write_text(
        "id,llegada,rafaga,prioridad,memoria_kb,cursos\nP001,0,5,2,128,SO101\nP002,1,0,1,96,SO101\n",
        encoding="utf-8",
    )
    codigo = punto_de_entrada.main(["procesos", "--escenario", str(csv_parcial)])
    capturado = capsys.readouterr()
    assert codigo == 1  # no es un éxito limpio: hubo un error
    assert "estado=completado_con_errores procesos=1 algoritmos=4 errores=1" in capturado.out
    assert "== Comparación" in capturado.out
    assert "[modulo1] error: línea 3" in capturado.err


def test_procesos_funciona_como_programa_desde_otro_directorio(tmp_path):
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / "main.py"), "procesos"], cwd=tmp_path, capture_output=True, text=True
    )
    assert resultado.returncode == 0, resultado.stderr
    assert ESTADO_COMPLETADO in resultado.stdout


@pytest.mark.skipif(shutil.which("make") is None, reason="make no está instalado")
def test_make_procesos_ejecuta_el_subcomando():
    resultado = subprocess.run(["make", "-s", "procesos"], cwd=RAIZ, capture_output=True, text=True, timeout=60)
    assert resultado.returncode == 0, resultado.stderr
    assert ESTADO_COMPLETADO in resultado.stdout


@pytest.mark.skipif(shutil.which("make") is None or shutil.which("gcc") is None, reason="se necesitan make y gcc")
def test_make_procesos_c_ejecuta_las_demos_en_c():
    resultado = subprocess.run(["make", "-s", "procesos-c"], cwd=RAIZ, capture_output=True, text=True, timeout=120)
    assert resultado.returncode == 0, resultado.stderr
    assert "0 zombies" in resultado.stdout and "join OK" in resultado.stdout


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
