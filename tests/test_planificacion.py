"""Pruebas de FCFS, SJF y Prioridad no expropiativos (Fase 4 del Módulo 1).

El oráculo de lote_pequeno.csv está calculado a mano en el WORKPLAN. Las
convenciones que fijan estas pruebas:
  - Prioridad: menor número = más prioritario. SJF y Prioridad desempatan por
    llegada y luego por id. FCFS desempata por id.
  - Si la CPU queda sin trabajo, el reloj salta a la siguiente llegada y el
    hueco queda registrado como segmento ocioso (pid None) y evento OCIOSA.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from core.cargador_escenarios import cargar_procesos
from core.modelos import Proceso, SimulationConfig
from collections import Counter

from modulo1_procesos.py import fcfs, prioridad, round_robin, sjf
from modulo1_procesos.py.diagrama import gantt_ascii, informe, lineas_de_log
from modulo1_procesos.py.motor import ResultadoPlanificacion, Segmento
from modulo1_procesos.py.cli import main
from modulo1_procesos.py.planificador import ALGORITMOS, comparar, planificar

ALGORITMOS_NO_EXPROPIATIVOS = [fcfs, sjf, prioridad]
NOMBRES = ["FCFS", "SJF", "PRIORIDAD"]
NOMBRES_CON_RR = NOMBRES + ["RR"]


def P(id, llegada, rafaga, prio=1):
    return Proceso(id, llegada, rafaga, prio, 64, ())


def lote_pequeno():
    return cargar_procesos("escenarios/lote_pequeno.csv")


def esperas(resultado):
    return {p.pid: p.espera for p in resultado.procesos}


def orden(resultado):
    return [s.pid for s in resultado.segmentos if s.pid is not None]


# --- Oráculo de lote_pequeno.csv ------------------------------------------


@pytest.mark.parametrize(
    "modulo, ordenado, espera_por_pid, espera_media, retorno_medio",
    [
        (fcfs, ["P001", "P002", "P003", "P004"], {"P001": 0, "P002": 4, "P003": 6, "P004": 11}, 5.25, 9.5),
        (sjf, ["P001", "P004", "P002", "P003"], {"P001": 0, "P002": 6, "P003": 8, "P004": 1}, 3.75, 8.0),
        (prioridad, ["P001", "P002", "P004", "P003"], {"P001": 0, "P002": 4, "P003": 8, "P004": 4}, 4.0, 8.25),
    ],
    ids=NOMBRES,
)
def test_oraculo_de_lote_pequeno(modulo, ordenado, espera_por_pid, espera_media, retorno_medio):
    r = modulo.planificar(lote_pequeno())
    assert orden(r) == ordenado
    assert esperas(r) == espera_por_pid
    assert r.espera_media == espera_media
    assert r.retorno_medio == retorno_medio


def test_fcfs_segmentos_exactos_de_lote_pequeno():
    r = fcfs.planificar(lote_pequeno())
    assert r.segmentos == (
        Segmento("P001", 0, 5),
        Segmento("P002", 5, 8),
        Segmento("P003", 8, 15),
        Segmento("P004", 15, 17),
    )


def test_sin_expropiacion_la_respuesta_es_igual_a_la_espera():
    for modulo in ALGORITMOS_NO_EXPROPIATIVOS:
        for p in modulo.planificar(lote_pequeno()).procesos:
            assert p.respuesta == p.espera


def test_cada_algoritmo_se_identifica_por_nombre():
    assert [m.planificar([]).algoritmo for m in ALGORITMOS_NO_EXPROPIATIVOS] == NOMBRES


# --- Casos límite: un solo proceso ----------------------------------------


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_un_solo_proceso_no_espera(modulo):
    r = modulo.planificar([P("P001", 0, 4)])
    assert r.segmentos == (Segmento("P001", 0, 4),)
    (p,) = r.procesos
    assert (p.espera, p.retorno, p.respuesta, p.inicio, p.fin) == (0, 4, 0, 0, 4)
    assert (r.espera_media, r.retorno_medio) == (0.0, 4.0)


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_un_proceso_que_llega_tarde_deja_ocioso_el_inicio(modulo):
    r = modulo.planificar([P("P001", 3, 4)])
    assert r.segmentos == (Segmento(None, 0, 3), Segmento("P001", 3, 7))
    assert r.procesos[0].espera == 0


# --- Casos límite: llegadas iguales ---------------------------------------

IGUALES = [P("P001", 0, 5, prio=2), P("P002", 0, 2, prio=3), P("P003", 0, 3, prio=1)]


@pytest.mark.parametrize(
    "modulo, ordenado, espera_por_pid",
    [
        (fcfs, ["P001", "P002", "P003"], {"P001": 0, "P002": 5, "P003": 7}),
        (sjf, ["P002", "P003", "P001"], {"P002": 0, "P003": 2, "P001": 5}),
        (prioridad, ["P003", "P001", "P002"], {"P003": 0, "P001": 3, "P002": 8}),
    ],
    ids=NOMBRES,
)
def test_llegadas_iguales(modulo, ordenado, espera_por_pid):
    r = modulo.planificar(IGUALES)
    assert orden(r) == ordenado
    assert esperas(r) == espera_por_pid


def test_fcfs_con_llegadas_iguales_desempata_por_id_aunque_la_lista_venga_desordenada():
    r = fcfs.planificar([P("P003", 0, 1), P("P001", 0, 1), P("P002", 0, 1)])
    assert orden(r) == ["P001", "P002", "P003"]


# --- Casos límite: CPU ociosa ---------------------------------------------


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_cpu_ociosa_entre_dos_procesos(modulo):
    r = modulo.planificar([P("P001", 0, 2), P("P002", 5, 1)])
    assert r.segmentos == (
        Segmento("P001", 0, 2),
        Segmento(None, 2, 5),
        Segmento("P002", 5, 6),
    )
    assert esperas(r) == {"P001": 0, "P002": 0}
    ociosos = [e for e in r.eventos if e.accion == "OCIOSA"]
    assert len(ociosos) == 1
    assert (ociosos[0].instante, ociosos[0].entidad, ociosos[0].datos["hasta"]) == (2, "CPU", 5)


# --- Casos límite: empates -------------------------------------------------


def test_sjf_desempata_ráfagas_iguales_por_llegada():
    # Al terminar P001 (t=4) esperan P003 (llegó en 1) y P002 (llegó en 2), ambos de ráfaga 3.
    r = sjf.planificar([P("P001", 0, 4), P("P002", 2, 3), P("P003", 1, 3)])
    assert orden(r) == ["P001", "P003", "P002"]


def test_sjf_desempata_ráfagas_y_llegadas_iguales_por_id():
    r = sjf.planificar([P("P001", 0, 4), P("P005", 1, 3), P("P004", 1, 3)])
    assert orden(r) == ["P001", "P004", "P005"]


def test_prioridad_desempata_prioridades_iguales_por_llegada():
    r = prioridad.planificar([P("P001", 0, 4, 2), P("P003", 2, 3, 1), P("P002", 1, 3, 1)])
    assert orden(r) == ["P001", "P002", "P003"]


def test_prioridad_desempata_prioridad_y_llegada_iguales_por_id():
    r = prioridad.planificar([P("P001", 0, 4, 2), P("P003", 1, 2, 1), P("P002", 1, 5, 1)])
    assert orden(r) == ["P001", "P002", "P003"]


# --- Casos límite: lista vacía ---------------------------------------------


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_lista_vacia_devuelve_resultado_vacio(modulo):
    r = modulo.planificar([])
    assert (r.procesos, r.segmentos, r.eventos) == ((), (), ())
    assert r.espera_media is None and r.retorno_medio is None


# --- Sin expropiación ------------------------------------------------------


def test_fcfs_ignora_rafaga_y_prioridad():
    r = fcfs.planificar([P("P001", 0, 10, 3), P("P002", 1, 1, 1)])
    assert orden(r) == ["P001", "P002"]


def test_sjf_no_interrumpe_al_proceso_en_cpu():
    r = sjf.planificar([P("P001", 0, 10), P("P002", 1, 1)])
    assert orden(r) == ["P001", "P002"]
    assert esperas(r)["P002"] == 9


def test_prioridad_no_interrumpe_al_proceso_en_cpu():
    r = prioridad.planificar([P("P001", 0, 10, 5), P("P002", 1, 1, 1)])
    assert orden(r) == ["P001", "P002"]


# --- Robustez de la entrada ------------------------------------------------


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_el_orden_de_entrada_no_cambia_el_resultado(modulo):
    normal = modulo.planificar(lote_pequeno())
    al_reves = modulo.planificar(tuple(reversed(lote_pequeno())))
    assert normal.segmentos == al_reves.segmentos
    assert esperas(normal) == esperas(al_reves)


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_no_modifica_la_lista_de_entrada(modulo):
    entrada = list(lote_pequeno())
    copia = list(entrada)
    modulo.planificar(entrada)
    assert entrada == copia


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_ids_duplicados_lanzan_value_error(modulo):
    with pytest.raises(ValueError, match="P001"):
        modulo.planificar([P("P001", 0, 1), P("P001", 1, 1)])


# --- Invariantes sobre lote_grande.csv -------------------------------------


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_invariantes_con_lote_grande(modulo):
    procesos = cargar_procesos("escenarios/lote_grande.csv")
    r = modulo.planificar(procesos)

    assert len(r.procesos) == len(procesos)
    for p in r.procesos:
        assert p.retorno == p.espera + p.rafaga
        assert p.inicio >= p.llegada
        assert p.fin - p.inicio == p.rafaga  # sin expropiación corre de corrido
    # Los segmentos cubren [0, fin] sin huecos ni solapes.
    assert r.segmentos[0].inicio == 0
    for anterior, siguiente in zip(r.segmentos, r.segmentos[1:]):
        assert anterior.fin == siguiente.inicio
    # La CPU solo trabaja lo que suman las ráfagas.
    ocupado = sum(s.fin - s.inicio for s in r.segmentos if s.pid is not None)
    assert ocupado == sum(p.rafaga for p in procesos)


# --- Eventos ---------------------------------------------------------------


def test_eventos_de_fcfs_en_lote_pequeno():
    r = fcfs.planificar(lote_pequeno())
    assert len(r.eventos) == 12  # 3 transiciones por proceso, sin huecos
    instantes = [e.instante for e in r.eventos]
    assert instantes == sorted(instantes)
    despachos = [
        (e.instante, e.entidad)
        for e in r.eventos
        if e.datos.get("hacia") == "EJECUCION"
    ]
    assert despachos == [(0, "P001"), (5, "P002"), (8, "P003"), (15, "P004")]
    assert all(e.modulo == "procesos" for e in r.eventos)


# --- Registro de algoritmos ------------------------------------------------


def test_el_registro_contiene_los_cuatro_algoritmos():
    assert list(ALGORITMOS) == NOMBRES_CON_RR


def test_el_registro_es_de_solo_lectura():
    with pytest.raises(TypeError):
        ALGORITMOS["RR"] = fcfs.planificar


@pytest.mark.parametrize("nombre", ["FCFS", "fcfs", " Fcfs "])
def test_planificar_acepta_el_nombre_sin_importar_mayusculas(nombre):
    assert planificar(nombre, lote_pequeno()).algoritmo == "FCFS"


def test_algoritmo_desconocido_lista_los_validos():
    with pytest.raises(ValueError, match=r"FCFS.*SJF.*PRIORIDAD"):
        planificar("ROUND_ROBIN_INEXISTENTE", lote_pequeno())


def test_comparar_corre_todos_con_el_mismo_escenario():
    resultados = comparar(lote_pequeno())
    assert list(resultados) == NOMBRES_CON_RR
    assert [r.espera_media for r in resultados.values()] == [5.25, 3.75, 4.0, 7.0]


def test_resultado_es_inmutable():
    r = fcfs.planificar(lote_pequeno())
    assert isinstance(r, ResultadoPlanificacion)
    with pytest.raises(AttributeError):
        r.algoritmo = "otro"


# --- Gantt ASCII -----------------------------------------------------------


def test_gantt_exacto_de_fcfs_en_lote_pequeno():
    # 2 caracteres por unidad de tiempo; cada marca de tiempo queda bajo su "|".
    r = fcfs.planificar(lote_pequeno())
    esperado_barra = "Gantt: |P001      |P002  |P003          |P004|"
    esperado_tiempos = " " * 7 + "0" + " " * 10 + "5" + " " * 6 + "8" + " " * 14 + "15" + " " * 3 + "17"
    assert gantt_ascii(r.segmentos).splitlines() == [esperado_barra, esperado_tiempos]


def test_gantt_marca_la_cpu_ociosa():
    r = fcfs.planificar([P("P001", 0, 2), P("P002", 5, 1)])
    barra = gantt_ascii(r.segmentos).splitlines()[0]
    assert barra == "Gantt: |P001|ocio  |P002|"


def test_gantt_ensancha_la_celda_si_el_nombre_no_cabe():
    # Un segmento de 1 unidad mediría 2 caracteres y "P001" necesita 4.
    barra = gantt_ascii(fcfs.planificar([P("P001", 0, 1)]).segmentos).splitlines()[0]
    assert barra == "Gantt: |P001|"


def test_gantt_sin_procesos():
    assert gantt_ascii(()) == "Gantt: (sin procesos)"


def test_gantt_no_pasa_de_una_linea_por_fila_ni_deja_espacios_al_final():
    for linea in gantt_ascii(fcfs.planificar(lote_pequeno()).segmentos).splitlines():
        assert linea == linea.rstrip()


# --- Log por algoritmo -----------------------------------------------------


def test_log_de_fcfs_tiene_las_lineas_clave():
    lineas = lineas_de_log(fcfs.planificar(lote_pequeno()))
    assert "[modulo1][t=000] FCFS  P001  NUEVO -> LISTO" in lineas
    assert "[modulo1][t=005] FCFS  P002  LISTO -> EJECUCION  (espera=4)" in lineas
    assert "[modulo1][t=008] FCFS  P002  EJECUCION -> TERMINADO" in lineas
    assert len(lineas) == 12


def test_log_registra_la_cpu_ociosa():
    lineas = lineas_de_log(fcfs.planificar([P("P001", 0, 2), P("P002", 5, 1)]))
    assert "[modulo1][t=002] FCFS  CPU  OCIOSA hasta t=5" in lineas


def test_informe_incluye_encabezado_gantt_tabla_y_medias():
    texto = informe(sjf.planificar(lote_pequeno()), escenario="lote_pequeno.csv")
    assert texto.splitlines()[0] == "== SJF | escenario=lote_pequeno.csv =="
    assert "Gantt: |P001" in texto
    assert "espera media=3.75 retorno medio=8.00" in texto
    assert "[modulo1][t=" not in texto  # el log por evento solo sale en modo detallado


def test_informe_detallado_agrega_el_log_por_evento():
    texto = informe(sjf.planificar(lote_pequeno()), verbose=True)
    assert "[modulo1][t=005] SJF  P004  LISTO -> EJECUCION  (espera=1)" in texto


def test_informe_de_lista_vacia_no_falla():
    texto = informe(fcfs.planificar([]))
    assert "Gantt: (sin procesos)" in texto
    assert "espera media=-" in texto


# --- Línea de comandos del planificador ------------------------------------


def test_main_muestra_un_algoritmo(capsys):
    codigo = main(["--algoritmo", "FCFS"])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "== FCFS | escenario=lote_pequeno.csv ==" in salida
    assert "espera media=5.25 retorno medio=9.50" in salida
    assert "== SJF" not in salida


def test_main_con_todos_muestra_los_tres_algoritmos(capsys):
    codigo = main(["--algoritmo", "todos"])
    salida = capsys.readouterr().out
    assert codigo == 0
    for nombre in NOMBRES + ["RR(q=2)"]:
        assert f"== {nombre} |" in salida


def test_main_acepta_otro_escenario(capsys):
    assert main(["--escenario", "escenarios/lote_grande.csv", "--algoritmo", "SJF"]) == 0
    assert "escenario=lote_grande.csv" in capsys.readouterr().out


def test_main_verbose_imprime_el_log_por_evento(capsys):
    main(["--algoritmo", "FCFS", "--verbose"])
    assert "[modulo1][t=005] FCFS  P002  LISTO -> EJECUCION  (espera=4)" in capsys.readouterr().out


def test_main_con_algoritmo_desconocido_devuelve_dos(capsys):
    assert main(["--algoritmo", "XYZ"]) == 2
    assert "FCFS" in capsys.readouterr().err


def test_main_con_escenario_invalido_devuelve_uno(tmp_path, capsys):
    malo = tmp_path / "malo.csv"
    malo.write_text("id,llegada,rafaga,prioridad,memoria_kb,cursos\nP001,0,0,1,64,\n", encoding="utf-8")
    assert main(["--escenario", str(malo)]) == 1
    assert "línea 2" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("make") is None, reason="make no está instalado")
def test_make_planificacion_ejecuta_el_planificador():
    raiz = Path(__file__).resolve().parent.parent
    resultado = subprocess.run(
        ["make", "-s", "planificacion"], cwd=raiz, capture_output=True, text=True, timeout=60
    )
    assert resultado.returncode == 0, resultado.stderr
    for nombre in NOMBRES + ["RR(q=2)"]:
        assert f"== {nombre} |" in resultado.stdout


# ===========================================================================
# Fase 5: Round Robin y coste de cambio de contexto
# ===========================================================================
#
# Reglas fijadas por estas pruebas:
#   - Cola FIFO. Un proceso expropiado vuelve al final de la cola.
#   - Si un proceso llega en el mismo instante en que otro agota su quantum,
#     el que llega entra primero a la cola.
#   - Hay cambio de contexto cuando la CPU pasa de un proceso a otro distinto
#     sin hueco ocioso entre ambos. Si el mismo proceso sigue, no hay cambio.
#   - El coste (config.cambio_contexto) ocupa la CPU durante ese cambio.

ORDEN_RR_Q2 = ["P001", "P002", "P003", "P001", "P004", "P002", "P003", "P001", "P003", "P003"]
ORDEN_RR_Q1 = [
    "P001", "P002", "P001", "P003", "P002", "P001", "P004", "P003", "P002",
    "P001", "P004", "P003", "P001", "P003", "P003", "P003", "P003",
]  # fmt: skip


def rr(procesos, quantum=2, cambio_contexto=0):
    config = SimulationConfig(quantum=quantum, cambio_contexto=cambio_contexto)
    return round_robin.planificar(procesos, config)


def fines(resultado):
    return {p.pid: p.fin for p in resultado.procesos}


def respuestas(resultado):
    return {p.pid: p.respuesta for p in resultado.procesos}


# --- Oráculo de lote_pequeno.csv con quantum 2 -----------------------------


def test_rr_oraculo_quantum_2_orden_de_las_rebanadas():
    assert orden(rr(lote_pequeno())) == ORDEN_RR_Q2


def test_rr_oraculo_quantum_2_segmentos_exactos():
    assert rr(lote_pequeno()).segmentos == (
        Segmento("P001", 0, 2),
        Segmento("P002", 2, 4),
        Segmento("P003", 4, 6),
        Segmento("P001", 6, 8),
        Segmento("P004", 8, 10),
        Segmento("P002", 10, 11),
        Segmento("P003", 11, 13),
        Segmento("P001", 13, 14),
        Segmento("P003", 14, 16),
        Segmento("P003", 16, 17),
    )


def test_rr_oraculo_quantum_2_instantes_de_fin():
    assert fines(rr(lote_pequeno())) == {"P001": 14, "P002": 11, "P003": 17, "P004": 10}


def test_rr_oraculo_quantum_2_esperas_y_media():
    r = rr(lote_pequeno())
    assert esperas(r) == {"P001": 9, "P002": 7, "P003": 8, "P004": 4}
    assert r.espera_media == 7.0
    assert r.retorno_medio == 11.25


def test_rr_oraculo_quantum_2_respuestas():
    assert respuestas(rr(lote_pequeno())) == {"P001": 0, "P002": 1, "P003": 2, "P004": 4}


def test_rr_oraculo_quantum_2_cambios_de_contexto():
    # 10 rebanadas dejan 9 pasos; en uno (P003 -> P003) sigue el mismo proceso.
    assert rr(lote_pequeno()).cambios_contexto == 8


def test_rr_el_nombre_incluye_el_quantum():
    assert rr(lote_pequeno(), quantum=2).algoritmo == "RR(q=2)"
    assert rr(lote_pequeno(), quantum=3).algoritmo == "RR(q=3)"


def test_rr_sin_config_usa_el_quantum_por_defecto():
    assert round_robin.planificar(lote_pequeno()).algoritmo == "RR(q=2)"


# --- Quantum 1 --------------------------------------------------------------


def test_rr_quantum_1_oraculo():
    r = rr(lote_pequeno(), quantum=1)
    assert orden(r) == ORDEN_RR_Q1
    assert all(s.fin - s.inicio == 1 for s in r.segmentos)
    assert fines(r) == {"P001": 13, "P002": 9, "P003": 17, "P004": 11}
    assert esperas(r) == {"P001": 8, "P002": 5, "P003": 8, "P004": 5}
    assert r.espera_media == 6.5
    assert respuestas(r) == {"P001": 0, "P002": 0, "P003": 1, "P004": 2}
    assert r.cambios_contexto == 13


# --- Quantum mayor o igual que la ráfaga más larga --------------------------


@pytest.mark.parametrize("quantum", [7, 8, 100])
def test_rr_con_quantum_grande_equivale_a_fcfs_en_lote_pequeno(quantum):
    r = rr(lote_pequeno(), quantum=quantum)
    f = fcfs.planificar(lote_pequeno())
    assert r.segmentos == f.segmentos
    assert esperas(r) == esperas(f)
    assert r.espera_media == f.espera_media
    assert r.cambios_contexto == f.cambios_contexto == 3


@pytest.mark.parametrize("quantum", [8, 9, 50])
def test_rr_con_quantum_grande_equivale_a_fcfs_en_lote_grande(quantum):
    procesos = cargar_procesos("escenarios/lote_grande.csv")  # ráfaga máxima: 8
    r = rr(procesos, quantum=quantum)
    f = fcfs.planificar(procesos)
    assert r.segmentos == f.segmentos
    assert esperas(r) == esperas(f)


# --- Quantum inválido -------------------------------------------------------


@pytest.mark.parametrize("quantum", [0, -1])
def test_quantum_no_positivo_es_un_error(quantum):
    # La configuración rechaza el valor antes de que llegue al planificador.
    with pytest.raises(ValueError, match="quantum"):
        SimulationConfig(quantum=quantum)


# --- Regla de llegada en el instante de expiración --------------------------


def test_rr_el_que_llega_al_expirar_el_quantum_entra_antes_que_el_expropiado():
    # P002 llega en t=2, justo cuando P001 agota su quantum con 2 unidades por
    # delante. Si P001 volviera primero a la cola, correría 2-4 y P002 esperaría.
    r = rr([P("P001", 0, 4), P("P002", 2, 2)])
    assert r.segmentos == (
        Segmento("P001", 0, 2),
        Segmento("P002", 2, 4),
        Segmento("P001", 4, 6),
    )


def test_rr_el_que_llega_durante_la_rebanada_tambien_entra_antes():
    # P002 llega en t=1, dentro de la rebanada de P001: a las 2 ya está en cola.
    r = rr([P("P001", 0, 4), P("P002", 1, 2)])
    assert orden(r) == ["P001", "P002", "P001"]


# --- Casos límite -----------------------------------------------------------


def test_rr_lista_vacia():
    r = rr([])
    assert (r.procesos, r.segmentos, r.eventos) == ((), (), ())
    assert r.espera_media is None and r.cambios_contexto == 0


def test_rr_un_solo_proceso_se_parte_en_rebanadas_sin_cambios_de_contexto():
    r = rr([P("P001", 0, 5)], quantum=2)
    assert r.segmentos == (Segmento("P001", 0, 2), Segmento("P001", 2, 4), Segmento("P001", 4, 5))
    assert r.cambios_contexto == 0
    assert (r.procesos[0].espera, r.procesos[0].respuesta) == (0, 0)


def test_rr_cpu_ociosa_entre_procesos():
    r = rr([P("P001", 0, 2), P("P002", 5, 1)])
    assert r.segmentos == (Segmento("P001", 0, 2), Segmento(None, 2, 5), Segmento("P002", 5, 6))
    assert r.cambios_contexto == 0  # el hueco ocioso rompe la continuidad


def test_rr_llegadas_iguales_siguen_el_orden_de_id():
    r = rr([P("P003", 0, 2), P("P001", 0, 2), P("P002", 0, 2)])
    assert orden(r) == ["P001", "P002", "P003"]


def test_rr_ids_duplicados_lanzan_value_error():
    with pytest.raises(ValueError, match="P001"):
        rr([P("P001", 0, 1), P("P001", 1, 1)])


def test_rr_no_modifica_la_lista_de_entrada():
    entrada = list(lote_pequeno())
    copia = list(entrada)
    rr(entrada)
    assert entrada == copia


def test_rr_el_orden_de_entrada_no_cambia_el_resultado():
    normal = rr(lote_pequeno())
    al_reves = rr(tuple(reversed(lote_pequeno())))
    assert normal.segmentos == al_reves.segmentos


# --- Invariantes de Round Robin sobre lote_grande.csv -----------------------


@pytest.mark.parametrize("quantum", [1, 2, 3, 5, 10])
def test_rr_invariantes_con_lote_grande(quantum):
    procesos = cargar_procesos("escenarios/lote_grande.csv")
    r = rr(procesos, quantum=quantum)

    for p in r.procesos:
        assert p.retorno == p.espera + p.rafaga
        assert p.inicio >= p.llegada
        assert p.respuesta == p.inicio - p.llegada
    # Cada proceso recibe de CPU exactamente su ráfaga, repartida en rebanadas.
    recibido = Counter()
    for s in r.segmentos:
        if s.pid is not None:
            recibido[s.pid] += s.fin - s.inicio
            assert s.fin - s.inicio <= quantum
    assert recibido == {p.id: p.rafaga for p in procesos}
    # Línea de tiempo continua desde 0, sin huecos ni solapes.
    assert r.segmentos[0].inicio == 0
    for anterior, siguiente in zip(r.segmentos, r.segmentos[1:]):
        assert anterior.fin == siguiente.inicio


# --- Eventos y log de Round Robin -------------------------------------------


def eventos_de(resultado, accion):
    return [e for e in resultado.eventos if e.accion == accion]


def test_rr_registra_una_expropiacion_por_rebanada_incompleta():
    r = rr(lote_pequeno())
    expropiaciones = eventos_de(r, "EXPROPIACION")
    assert len(expropiaciones) == 6  # 10 rebanadas, 4 de ellas terminan al proceso
    primera = expropiaciones[0]
    assert (primera.instante, primera.entidad) == (2, "P001")
    assert primera.datos["restante"] == 3
    assert primera.datos["cola"] == ("P002", "P003", "P001")


def test_rr_los_eventos_salen_en_orden_de_tiempo():
    instantes = [e.instante for e in rr(lote_pequeno()).eventos]
    assert instantes == sorted(instantes)


def test_log_de_rr_muestra_expropiaciones_con_el_estado_de_la_cola():
    lineas = lineas_de_log(rr(lote_pequeno()))
    assert "[modulo1][t=002] RR(q=2)  P001  EXPROPIADO (restante=3) -> cola=[P002,P003,P001]" in lineas
    assert "[modulo1][t=004] RR(q=2)  P002  EXPROPIADO (restante=1) -> cola=[P003,P001,P004,P002]" in lineas


def test_log_de_rr_anota_la_espera_solo_en_el_primer_despacho():
    lineas = lineas_de_log(rr(lote_pequeno()))
    assert "[modulo1][t=008] RR(q=2)  P004  LISTO -> EJECUCION  (espera=4)" in lineas
    assert "[modulo1][t=006] RR(q=2)  P001  LISTO -> EJECUCION" in lineas  # segundo despacho


def test_log_de_rr_no_repite_la_expropiacion_como_transicion_suelta():
    lineas = lineas_de_log(rr(lote_pequeno()))
    assert not any("EJECUCION -> LISTO" in linea for linea in lineas)


def test_log_de_rr_marca_el_fin_de_cada_proceso():
    lineas = lineas_de_log(rr(lote_pequeno()))
    assert "[modulo1][t=010] RR(q=2)  P004  EJECUCION -> TERMINADO" in lineas
    assert "[modulo1][t=017] RR(q=2)  P003  EJECUCION -> TERMINADO" in lineas


def test_informe_de_rr_incluye_cambios_de_contexto():
    texto = informe(rr(lote_pequeno()), escenario="lote_pequeno.csv")
    assert texto.splitlines()[0] == "== RR(q=2) | escenario=lote_pequeno.csv =="
    assert "espera media=7.00 retorno medio=11.25 cambios de contexto=8" in texto


# --- Cambios de contexto en los algoritmos sin expropiación -----------------


@pytest.mark.parametrize("modulo", ALGORITMOS_NO_EXPROPIATIVOS, ids=NOMBRES)
def test_cambios_de_contexto_de_los_algoritmos_sin_expropiacion(modulo):
    assert modulo.planificar(lote_pequeno()).cambios_contexto == 3
    assert modulo.planificar([P("P001", 0, 3)]).cambios_contexto == 0


# --- Coste de cambio de contexto (config.cambio_contexto) -------------------


def test_fcfs_con_coste_inserta_segmentos_de_cambio_de_contexto():
    r = fcfs.planificar(lote_pequeno(), SimulationConfig(cambio_contexto=1))
    cambio = lambda a, b: Segmento(None, a, b, cambio_contexto=True)  # noqa: E731
    assert r.segmentos == (
        Segmento("P001", 0, 5),
        cambio(5, 6),
        Segmento("P002", 6, 9),
        cambio(9, 10),
        Segmento("P003", 10, 17),
        cambio(17, 18),
        Segmento("P004", 18, 20),
    )
    assert esperas(r) == {"P001": 0, "P002": 5, "P003": 8, "P004": 14}
    assert r.cambios_contexto == 3


def test_el_coste_genera_un_evento_por_cambio():
    r = fcfs.planificar(lote_pequeno(), SimulationConfig(cambio_contexto=1))
    eventos = eventos_de(r, "CAMBIO_CONTEXTO")
    assert len(eventos) == 3
    assert (eventos[0].instante, eventos[0].entidad) == (5, "CPU")
    assert eventos[0].datos == {"de": "P001", "a": "P002", "costo": 1}


def test_sin_coste_no_hay_eventos_ni_segmentos_de_cambio():
    r = fcfs.planificar(lote_pequeno())
    assert eventos_de(r, "CAMBIO_CONTEXTO") == []
    assert not any(s.cambio_contexto for s in r.segmentos)


def test_rr_con_coste_exacto_en_un_caso_pequeno():
    r = rr([P("P001", 0, 4), P("P002", 0, 4)], quantum=2, cambio_contexto=1)
    cambio = lambda a, b: Segmento(None, a, b, cambio_contexto=True)  # noqa: E731
    assert r.segmentos == (
        Segmento("P001", 0, 2),
        cambio(2, 3),
        Segmento("P002", 3, 5),
        cambio(5, 6),
        Segmento("P001", 6, 8),
        cambio(8, 9),
        Segmento("P002", 9, 11),
    )
    assert fines(r) == {"P001": 8, "P002": 11}
    assert esperas(r) == {"P001": 4, "P002": 7}
    assert r.cambios_contexto == 3


@pytest.mark.parametrize("nombre", ["FCFS", "SJF", "PRIORIDAD", "RR"])
@pytest.mark.parametrize("coste", [1, 3])
def test_el_tiempo_total_es_la_suma_de_rafagas_mas_el_coste_de_los_cambios(nombre, coste):
    procesos = lote_pequeno()  # sin huecos ociosos: la CPU siempre tiene trabajo
    r = planificar(nombre, procesos, SimulationConfig(cambio_contexto=coste))
    total = r.segmentos[-1].fin
    assert total == sum(p.rafaga for p in procesos) + coste * r.cambios_contexto
    duracion_cambios = sum(s.fin - s.inicio for s in r.segmentos if s.cambio_contexto)
    assert duracion_cambios == coste * r.cambios_contexto
    for anterior, siguiente in zip(r.segmentos, r.segmentos[1:]):
        assert anterior.fin == siguiente.inicio


def test_no_se_cobra_cambio_de_contexto_a_traves_de_un_hueco_ocioso():
    r = fcfs.planificar([P("P001", 0, 2), P("P002", 5, 1)], SimulationConfig(cambio_contexto=3))
    assert r.segmentos == (Segmento("P001", 0, 2), Segmento(None, 2, 5), Segmento("P002", 5, 6))
    assert r.cambios_contexto == 0


def test_las_llegadas_durante_un_cambio_de_contexto_se_admiten_en_orden():
    # P003 llega en t=3, a mitad del cambio P001 -> P002 (2 a 4).
    r = fcfs.planificar(
        [P("P001", 0, 2), P("P002", 0, 2), P("P003", 3, 1)], SimulationConfig(cambio_contexto=2)
    )
    instantes = [e.instante for e in r.eventos]
    assert instantes == sorted(instantes)
    llegada_p003 = next(e for e in r.eventos if e.entidad == "P003" and e.datos.get("hacia") == "LISTO")
    despacho_p002 = next(e for e in r.eventos if e.entidad == "P002" and e.datos.get("hacia") == "EJECUCION")
    assert (llegada_p003.instante, despacho_p002.instante) == (3, 4)
    assert r.segmentos[-1] == Segmento("P003", 8, 9)


def test_un_segmento_de_cambio_de_contexto_no_puede_tener_proceso():
    with pytest.raises(ValueError):
        Segmento("P001", 0, 1, cambio_contexto=True)


def test_gantt_muestra_los_cambios_de_contexto_como_ctx():
    r = fcfs.planificar(lote_pequeno(), SimulationConfig(cambio_contexto=1))
    barra, tiempos = gantt_ascii(r.segmentos).splitlines()
    assert barra == "Gantt: |P001      |ctx|P002  |ctx|P003          |ctx|P004|"
    esperado = "0" + " " * 10 + "5" + " " * 3 + "6" + " " * 6 + "9" + " " * 3 + "10" + " " * 13 + "17" + " " * 2 + "18" + " " * 3 + "20"
    assert tiempos == " " * 7 + esperado


def test_log_registra_el_cambio_de_contexto():
    lineas = lineas_de_log(fcfs.planificar(lote_pequeno(), SimulationConfig(cambio_contexto=1)))
    assert "[modulo1][t=005] FCFS  CPU  CAMBIO_CONTEXTO P001 -> P002 (costo=1)" in lineas


# --- Registro y línea de comandos con Round Robin ---------------------------


@pytest.mark.parametrize("nombre", ["RR", "rr", " Rr "])
def test_planificar_por_nombre_acepta_rr(nombre):
    assert planificar(nombre, lote_pequeno()).algoritmo == "RR(q=2)"
    assert planificar(nombre, lote_pequeno(), SimulationConfig(quantum=4)).algoritmo == "RR(q=4)"


def test_algoritmo_desconocido_tambien_lista_rr():
    with pytest.raises(ValueError, match=r"PRIORIDAD, RR"):
        planificar("XYZ", lote_pequeno())


def test_main_rr_usa_el_quantum_indicado(capsys):
    assert main(["--algoritmo", "RR", "--quantum", "3"]) == 0
    assert "== RR(q=3) | escenario=lote_pequeno.csv ==" in capsys.readouterr().out


def test_main_rr_verbose_muestra_las_expropiaciones(capsys):
    main(["--algoritmo", "RR", "--verbose"])
    assert "P001  EXPROPIADO (restante=3) -> cola=[P002,P003,P001]" in capsys.readouterr().out


@pytest.mark.parametrize("quantum", ["0", "-1", "abc"])
def test_main_rechaza_un_quantum_invalido(quantum, capsys):
    assert main(["--algoritmo", "RR", "--quantum", quantum]) == 2
    assert capsys.readouterr().err != ""


def test_main_acepta_coste_de_cambio_de_contexto(capsys):
    assert main(["--algoritmo", "FCFS", "--cambio-contexto", "1"]) == 0
    salida = capsys.readouterr().out
    assert "ctx" in salida and "cambios de contexto=3" in salida


def test_main_rechaza_un_coste_negativo(capsys):
    assert main(["--cambio-contexto", "-1"]) == 2
    assert "cambio_contexto" in capsys.readouterr().err
