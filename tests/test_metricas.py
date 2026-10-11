"""Pruebas de core/metricas.py: promedio, exportación CSV/JSON y tabla de consola."""

import csv
import json
from pathlib import Path

import pytest

from core.metricas import exportar_csv, exportar_json, formatear_tabla, promedio


# ---------------------------------------------------------------- promedio


def test_promedio_de_enteros_devuelve_media_aritmetica():
    assert promedio([2, 4, 6]) == 4.0


def test_promedio_de_floats():
    assert promedio([1.5, 2.5]) == 2.0


def test_promedio_mezcla_enteros_y_floats():
    assert promedio([1, 2.0, 3]) == 2.0


def test_promedio_acepta_iterables_no_secuencia():
    assert promedio(x for x in (1, 2, 3)) == 2.0


def test_promedio_vacio_falla():
    with pytest.raises(ValueError):
        promedio([])


def test_promedio_rechaza_bool():
    with pytest.raises(ValueError):
        promedio([1, True])


def test_promedio_rechaza_texto():
    with pytest.raises(ValueError):
        promedio([1, "2"])


def test_promedio_rechaza_none():
    with pytest.raises(ValueError):
        promedio([1, None])


# ------------------------------------------------------------- exportar_csv


def _leer_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def test_csv_escribe_cabecera_y_filas_con_claves_de_la_primera_fila(tmp_path):
    filas = [{"b": 1, "a": 2}, {"b": 3, "a": 4}]
    destino = tmp_path / "salida.csv"
    exportar_csv(filas, destino)
    assert _leer_csv(destino) == [["b", "a"], ["1", "2"], ["3", "4"]]


def test_csv_devuelve_el_path_escrito(tmp_path):
    destino = tmp_path / "salida.csv"
    resultado = exportar_csv([{"a": 1}], destino)
    assert resultado == destino
    assert isinstance(resultado, Path)


def test_csv_acepta_ruta_como_str(tmp_path):
    destino = tmp_path / "salida.csv"
    resultado = exportar_csv([{"a": 1}], str(destino))
    assert resultado == destino
    assert destino.exists()


def test_csv_respeta_el_orden_de_columnas_indicado(tmp_path):
    destino = tmp_path / "salida.csv"
    exportar_csv([{"a": 1, "b": 2}], destino, columnas=["b", "a"])
    assert _leer_csv(destino) == [["b", "a"], ["2", "1"]]


def test_csv_ignora_claves_no_listadas_en_columnas(tmp_path):
    destino = tmp_path / "salida.csv"
    exportar_csv([{"a": 1, "b": 2, "c": 3}], destino, columnas=["a", "c"])
    assert _leer_csv(destino) == [["a", "c"], ["1", "3"]]


def test_csv_escribe_cadena_vacia_si_falta_una_clave(tmp_path):
    destino = tmp_path / "salida.csv"
    exportar_csv([{"a": 1, "b": 2}, {"a": 3}], destino)
    assert _leer_csv(destino) == [["a", "b"], ["1", "2"], ["3", ""]]


def test_csv_sin_filas_pero_con_columnas_escribe_solo_cabecera(tmp_path):
    destino = tmp_path / "salida.csv"
    exportar_csv([], destino, columnas=["a", "b"])
    assert _leer_csv(destino) == [["a", "b"]]


def test_csv_sin_filas_y_sin_columnas_falla(tmp_path):
    with pytest.raises(ValueError):
        exportar_csv([], tmp_path / "salida.csv")


def test_csv_sin_filas_y_sin_columnas_no_deja_archivo(tmp_path):
    destino = tmp_path / "salida.csv"
    with pytest.raises(ValueError):
        exportar_csv([], destino)
    assert not destino.exists()


def test_csv_crea_directorios_padre_anidados(tmp_path):
    destino = tmp_path / "uno" / "dos" / "salida.csv"
    exportar_csv([{"a": 1}], destino)
    assert destino.is_file()


def test_csv_escribe_utf8_sin_lineas_en_blanco_extra(tmp_path):
    destino = tmp_path / "salida.csv"
    exportar_csv([{"nombre": "ñandú"}, {"nombre": "café"}], destino)
    crudo = destino.read_bytes()
    assert "ñandú".encode("utf-8") in crudo
    # newline="" evita que el módulo csv duplique el \r en Windows.
    assert b"\r\r" not in crudo
    assert _leer_csv(destino) == [["nombre"], ["ñandú"], ["café"]]


def test_csv_round_trip_con_dictreader(tmp_path):
    filas = [{"id": "P1", "espera": 5}, {"id": "P2", "espera": 7}]
    destino = tmp_path / "salida.csv"
    exportar_csv(filas, destino)
    with open(destino, encoding="utf-8", newline="") as f:
        leidas = list(csv.DictReader(f))
    assert leidas == [{"id": "P1", "espera": "5"}, {"id": "P2", "espera": "7"}]


# ------------------------------------------------------------ exportar_json


def test_json_round_trip(tmp_path):
    datos = {"algoritmo": "FCFS", "espera": [1, 2.5], "ok": True, "nada": None}
    destino = tmp_path / "salida.json"
    exportar_json(datos, destino)
    assert json.loads(destino.read_text(encoding="utf-8")) == datos


def test_json_devuelve_el_path_escrito(tmp_path):
    destino = tmp_path / "salida.json"
    resultado = exportar_json({"a": 1}, str(destino))
    assert resultado == destino
    assert isinstance(resultado, Path)


def test_json_usa_indent_2_y_salto_de_linea_final(tmp_path):
    destino = tmp_path / "salida.json"
    exportar_json({"a": 1}, destino)
    assert destino.read_text(encoding="utf-8") == '{\n  "a": 1\n}\n'


def test_json_conserva_caracteres_no_ascii(tmp_path):
    destino = tmp_path / "salida.json"
    exportar_json({"nombre": "planificación"}, destino)
    assert "planificación" in destino.read_text(encoding="utf-8")


def test_json_crea_directorios_padre_anidados(tmp_path):
    destino = tmp_path / "uno" / "dos" / "salida.json"
    exportar_json([1, 2], destino)
    assert destino.is_file()


def test_json_no_serializable_falla_con_type_error(tmp_path):
    with pytest.raises(TypeError):
        exportar_json({"conjunto": {1, 2}}, tmp_path / "salida.json")


def test_json_no_serializable_no_deja_archivo_a_medias(tmp_path):
    destino = tmp_path / "salida.json"
    with pytest.raises(TypeError):
        exportar_json({"ok": 1, "mal": object()}, destino)
    assert not destino.exists()


def test_json_no_serializable_conserva_el_archivo_previo(tmp_path):
    destino = tmp_path / "salida.json"
    destino.write_text("previo", encoding="utf-8")
    with pytest.raises(TypeError):
        exportar_json({"mal": object()}, destino)
    assert destino.read_text(encoding="utf-8") == "previo"


# ----------------------------------------------------------- formatear_tabla


def test_tabla_ejemplo_de_referencia():
    filas = [
        {"algoritmo": "FCFS", "espera": 5.25, "retorno": 9.5},
        {"algoritmo": "SJF", "espera": 3.75, "retorno": 8},
    ]
    esperado = (
        "algoritmo  espera  retorno\n"
        "---------  ------  -------\n"
        "FCFS         5.25     9.50\n"
        "SJF          3.75     8.00"
    )
    assert formatear_tabla(["algoritmo", "espera", "retorno"], filas) == esperado


def test_tabla_alinea_texto_a_la_izquierda():
    salida = formatear_tabla(["nombre"], [{"nombre": "ab"}, {"nombre": "abcd"}])
    assert salida.splitlines()[2] == "ab"
    assert salida.splitlines()[3] == "abcd"


def test_tabla_alinea_numeros_a_la_derecha():
    salida = formatear_tabla(["n"], [{"n": 1}, {"n": 1000}])
    assert salida.splitlines()[2:] == ["   1", "1000"]


def test_tabla_alinea_cabecera_numerica_a_la_derecha():
    # Regla documentada: la cabecera sigue la alineación de su columna.
    salida = formatear_tabla(["total"], [{"total": "texto largo"}])
    assert salida.splitlines()[0] == "total"
    salida = formatear_tabla(["n"], [{"n": 123456}])
    assert salida.splitlines()[0] == "     n"


def test_tabla_alinea_cabecera_de_texto_a_la_izquierda():
    salida = formatear_tabla(["a", "b"], [{"a": "xxxx", "b": "y"}])
    assert salida.splitlines()[0] == "a     b"


def test_tabla_formatea_floats_con_dos_decimales():
    salida = formatear_tabla(["x"], [{"x": 2.0}, {"x": 3.14159}])
    assert salida.splitlines()[2:] == ["2.00", "3.14"]


def test_tabla_columna_con_un_float_muestra_los_enteros_con_dos_decimales():
    salida = formatear_tabla(["x"], [{"x": 9.5}, {"x": 8}])
    assert salida.splitlines()[2:] == ["9.50", "8.00"]


def test_tabla_enteros_se_muestran_sin_decimales():
    salida = formatear_tabla(["x"], [{"x": 7}])
    assert salida.splitlines()[2] == "7"


def test_tabla_clave_ausente_se_muestra_como_guion():
    salida = formatear_tabla(["a", "b"], [{"a": "x"}])
    assert salida.splitlines()[2] == "x  -"


def test_tabla_clave_ausente_en_columna_numerica_se_alinea_a_la_derecha():
    salida = formatear_tabla(["n"], [{"n": 100}, {}])
    assert salida.splitlines()[2:] == ["100", "  -"]


def test_tabla_sin_filas_devuelve_cabecera_y_separador():
    salida = formatear_tabla(["abc", "de"], [])
    assert salida == "abc  de\n---  --"


def test_tabla_sin_columnas_falla():
    with pytest.raises(ValueError):
        formatear_tabla([], [{"a": 1}])


def test_tabla_sin_espacios_sobrantes_al_final_de_cada_linea():
    filas = [{"a": "x", "b": "larguisimo"}, {"a": "yyyy", "b": "z"}]
    for linea in formatear_tabla(["a", "b"], filas).splitlines():
        assert linea == linea.rstrip()


def test_tabla_ancho_es_el_maximo_entre_cabecera_y_celdas():
    salida = formatear_tabla(["id"], [{"id": "P1000"}])
    assert salida.splitlines()[1] == "-----"


def test_tabla_ignora_claves_de_la_fila_no_listadas():
    salida = formatear_tabla(["a"], [{"a": 1, "b": 2}])
    assert salida.splitlines() == ["a", "-", "1"]


def test_tabla_bool_se_trata_como_texto():
    salida = formatear_tabla(["ok"], [{"ok": True}])
    assert salida.splitlines()[2] == "True"
