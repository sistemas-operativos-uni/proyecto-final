"""Pruebas del cargador de escenarios CSV."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cargador_escenarios import (
    CargaProcesos,
    ErrorEscenario,
    cargar_procesos,
    cargar_procesos_tolerante,
)
from core.modelos import Proceso

CABECERA = "id,llegada,rafaga,prioridad,memoria_kb,cursos"
RAIZ = Path(__file__).resolve().parent.parent
ESCENARIOS = RAIZ / "escenarios"


def escribir(tmp_path: Path, *lineas: str, nombre: str = "lote.csv") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="")
    return ruta


# --- Aceptación con los CSV reales ---------------------------------------


def test_lote_pequeno_tiene_cuatro_procesos():
    carga = cargar_procesos_tolerante(ESCENARIOS / "lote_pequeno.csv")
    assert len(carga.procesos) == 4
    assert carga.errores == ()


def test_lote_pequeno_p004_llega_en_4_con_rafaga_2():
    p004 = cargar_procesos(ESCENARIOS / "lote_pequeno.csv")[3]
    assert p004.id == "P004"
    assert p004.llegada == 4
    assert p004.rafaga == 2


def test_lote_grande_tiene_diez_procesos_sin_errores():
    carga = cargar_procesos_tolerante(ESCENARIOS / "lote_grande.csv")
    assert len(carga.procesos) == 10
    assert carga.errores == ()


# --- Lectura básica ------------------------------------------------------


def test_devuelve_proceso_con_todos_los_campos(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,SO101;BD202")
    carga = cargar_procesos_tolerante(ruta)
    assert isinstance(carga, CargaProcesos)
    assert carga.procesos == (Proceso("P001", 0, 5, 2, 128, ("SO101", "BD202")),)


def test_mantiene_el_orden_del_archivo(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "B,0,1,0,1,", "A,1,1,0,1,", "C,2,1,0,1,")
    assert [p.id for p in cargar_procesos(ruta)] == ["B", "A", "C"]


def test_acepta_ruta_como_str(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,SO101")
    assert len(cargar_procesos(str(ruta))) == 1
    assert len(cargar_procesos_tolerante(str(ruta)).procesos) == 1


def test_tolera_bom_al_inicio(tmp_path):
    ruta = tmp_path / "bom.csv"
    ruta.write_bytes(("﻿" + CABECERA + "\nP001,0,5,2,128,SO101\n").encode("utf-8"))
    assert cargar_procesos(ruta)[0].id == "P001"


def test_lee_utf8(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,Álgebra;Cálculo")
    assert cargar_procesos(ruta)[0].cursos == ("Álgebra", "Cálculo")


def test_ignora_columnas_extra_en_la_cabecera(tmp_path):
    ruta = escribir(
        tmp_path,
        "nota," + CABECERA,
        "x,P001,0,5,2,128,SO101",
    )
    proceso = cargar_procesos(ruta)[0]
    assert proceso == Proceso("P001", 0, 5, 2, 128, ("SO101",))


def test_acepta_columnas_en_otro_orden(tmp_path):
    ruta = escribir(
        tmp_path,
        "cursos,memoria_kb,prioridad,rafaga,llegada,id",
        "SO101,128,2,5,0,P001",
    )
    assert cargar_procesos(ruta)[0] == Proceso("P001", 0, 5, 2, 128, ("SO101",))


# --- Cursos --------------------------------------------------------------


def test_cursos_recorta_espacios(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128, SO101 ; BD202 ")
    assert cargar_procesos(ruta)[0].cursos == ("SO101", "BD202")


def test_cursos_descarta_elementos_vacios(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,SO101;;  ;BD202;")
    assert cargar_procesos(ruta)[0].cursos == ("SO101", "BD202")


def test_cursos_vacio_da_tupla_vacia(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,")
    assert cargar_procesos(ruta)[0].cursos == ()


# --- Errores de fila (tolerante) -----------------------------------------


@pytest.mark.parametrize(
    "fila, columna",
    [
        ("P001,x,5,2,128,", "llegada"),
        ("P001,0,5.5,2,128,", "rafaga"),
        ("P001,0,5,alta,128,", "prioridad"),
        ("P001,0,5,2,,", "memoria_kb"),
    ],
)
def test_valor_no_entero_se_reporta_con_su_columna(tmp_path, fila, columna):
    ruta = escribir(tmp_path, CABECERA, fila)
    carga = cargar_procesos_tolerante(ruta)
    assert carga.procesos == ()
    assert len(carga.errores) == 1
    assert carga.errores[0].startswith("línea 2: ")
    assert columna in carga.errores[0]


def test_rafaga_cero_se_rechaza_con_el_motivo_del_modelo(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,0,2,128,")
    carga = cargar_procesos_tolerante(ruta)
    assert carga.procesos == ()
    assert carga.errores == ("línea 2: rafaga debe ser >= 1, recibió 0",)


def test_id_vacio_se_rechaza(tmp_path):
    ruta = escribir(tmp_path, CABECERA, " ,0,5,2,128,")
    carga = cargar_procesos_tolerante(ruta)
    assert carga.errores == ("línea 2: id no puede estar vacío",)


def test_valor_negativo_se_rechaza(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,-1,5,2,128,")
    carga = cargar_procesos_tolerante(ruta)
    assert carga.errores == ("línea 2: llegada debe ser >= 0, recibió -1",)


def test_id_duplicado_conserva_el_primero_y_rechaza_el_repetido(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,", "P002,1,3,1,96,", "P001,9,9,9,9,")
    carga = cargar_procesos_tolerante(ruta)
    assert [(p.id, p.llegada) for p in carga.procesos] == [("P001", 0), ("P002", 1)]
    assert len(carga.errores) == 1
    assert carga.errores[0].startswith("línea 4: ")
    assert "P001" in carga.errores[0]


def test_fila_con_columnas_de_mas_se_rechaza(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,SO101,sobra")
    carga = cargar_procesos_tolerante(ruta)
    assert carga.procesos == ()
    assert len(carga.errores) == 1
    assert carga.errores[0].startswith("línea 2: ")
    assert "7" in carga.errores[0] and "6" in carga.errores[0]


def test_fila_con_columnas_de_menos_se_rechaza(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5")
    carga = cargar_procesos_tolerante(ruta)
    assert carga.procesos == ()
    assert len(carga.errores) == 1
    assert carga.errores[0].startswith("línea 2: ")
    assert "3" in carga.errores[0] and "6" in carga.errores[0]


def test_tolerante_conserva_validas_y_numera_lineas_del_archivo(tmp_path):
    ruta = escribir(
        tmp_path,
        CABECERA,
        "P001,0,5,2,128,",
        "P002,x,3,1,96,",
        "P003,2,7,3,160,",
        "P004,3,0,1,64,",
    )
    carga = cargar_procesos_tolerante(ruta)
    assert [p.id for p in carga.procesos] == ["P001", "P003"]
    assert [e[:8] for e in carga.errores] == ["línea 3:", "línea 5:"]


def test_numeracion_cuenta_las_lineas_en_blanco(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,", "", "P002,x,3,1,96,")
    carga = cargar_procesos_tolerante(ruta)
    assert len(carga.procesos) == 1
    assert carga.errores[0].startswith("línea 4: ")


def test_numeracion_cuenta_campos_entrecomillados_con_salto_de_linea(tmp_path):
    ruta = escribir(
        tmp_path,
        CABECERA,
        'P001,0,5,2,128,"SO101',
        'BD202"',
        "P002,x,3,1,96,",
    )
    carga = cargar_procesos_tolerante(ruta)
    assert carga.errores[0].startswith("línea 4: ")


# --- Versión estricta ----------------------------------------------------


def test_estricta_lanza_con_todos_los_mensajes_unidos_por_salto_de_linea(tmp_path):
    ruta = escribir(tmp_path, CABECERA, "P001,0,5,2,128,", "P002,x,3,1,96,", "P003,2,0,3,160,")
    with pytest.raises(ErrorEscenario) as info:
        cargar_procesos(ruta)
    lineas = str(info.value).split("\n")
    assert len(lineas) == 2
    assert lineas[0].startswith("línea 3: ")
    assert lineas[1].startswith("línea 4: ")


def test_estricta_lanza_si_no_hay_ningun_proceso_valido(tmp_path):
    ruta = escribir(tmp_path, CABECERA)
    with pytest.raises(ErrorEscenario, match="ningún proceso"):
        cargar_procesos(ruta)


def test_tolerante_con_solo_cabecera_devuelve_vacio_sin_errores(tmp_path):
    carga = cargar_procesos_tolerante(escribir(tmp_path, CABECERA))
    assert carga == CargaProcesos(procesos=(), errores=())


# --- Errores de archivo (ambas versiones) --------------------------------


@pytest.mark.parametrize("funcion", [cargar_procesos, cargar_procesos_tolerante])
def test_archivo_inexistente_lanza_error_escenario(tmp_path, funcion):
    with pytest.raises(ErrorEscenario, match="no existe"):
        funcion(tmp_path / "no_existe.csv")


@pytest.mark.parametrize("funcion", [cargar_procesos, cargar_procesos_tolerante])
def test_archivo_vacio_lanza_error_escenario(tmp_path, funcion):
    ruta = tmp_path / "vacio.csv"
    ruta.write_text("", encoding="utf-8")
    with pytest.raises(ErrorEscenario, match="vacío"):
        funcion(ruta)


@pytest.mark.parametrize("funcion", [cargar_procesos, cargar_procesos_tolerante])
def test_cabecera_sin_columnas_obligatorias_nombra_las_que_faltan(tmp_path, funcion):
    ruta = escribir(tmp_path, "id,llegada,prioridad,cursos", "P001,0,2,SO101")
    with pytest.raises(ErrorEscenario) as info:
        funcion(ruta)
    mensaje = str(info.value)
    assert "rafaga" in mensaje
    assert "memoria_kb" in mensaje
    assert "llegada" not in mensaje


@pytest.mark.parametrize("funcion", [cargar_procesos, cargar_procesos_tolerante])
def test_ruta_que_es_directorio_lanza_error_escenario(tmp_path, funcion):
    with pytest.raises(ErrorEscenario):
        funcion(tmp_path)


@pytest.mark.parametrize("funcion", [cargar_procesos, cargar_procesos_tolerante])
def test_archivo_no_utf8_lanza_error_escenario(tmp_path, funcion):
    ruta = tmp_path / "latin1.csv"
    ruta.write_bytes((CABECERA + "\nP001,0,5,2,128,Álgebra\n").encode("latin-1"))
    with pytest.raises(ErrorEscenario, match="UTF-8"):
        funcion(ruta)
