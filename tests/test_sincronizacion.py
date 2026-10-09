"""Pruebas del Modulo 2: sincronizacion de procesos (lectores-escritores y semaforos).

Compilan los programas de ``modulo2_sincronizacion/c`` con gcc, los ejecutan y
validan su traza CSV (``instante,modulo,entidad,accion,datos``) contra el
criterio de cierre del modulo: no hay escrituras simultaneas ni corrupcion del
padron, y el orden de eventos se puede reconstruir desde la traza.

Ejecutar desde la raiz del repositorio:  python -m pytest tests/test_sincronizacion.py -v
"""

from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

DIRECTORIO_C = Path(__file__).resolve().parent.parent / "modulo2_sincronizacion" / "c"
BANDERAS_BASE = ["-std=c11", "-Wall", "-Wextra", "-pthread"]
TIEMPO_MAXIMO_S = 60

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="El modulo usa semaforos POSIX sin nombre (Linux).",
)


# ---------------------------------------------------------------------------
# Compilacion y ejecucion
# ---------------------------------------------------------------------------


def _compilador() -> str | None:
    return shutil.which(os.environ.get("CC", "gcc"))


def compilar(fuente: str, salida: Path, extras: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    cc = _compilador()
    if cc is None:
        pytest.skip("No hay compilador C (gcc) disponible.")
    return subprocess.run(
        [cc, *BANDERAS_BASE, *extras, "-o", str(salida), str(DIRECTORIO_C / fuente)],
        capture_output=True,
        text=True,
        timeout=TIEMPO_MAXIMO_S,
    )


@pytest.fixture(scope="module")
def directorio_bin(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("bin_sincronizacion")


@pytest.fixture(scope="module")
def lectores_escritores(directorio_bin) -> Path:
    destino = directorio_bin / "lectores_escritores"
    resultado = compilar("lectores_escritores.c", destino, ("-O2",))
    assert resultado.returncode == 0, resultado.stderr
    return destino


@pytest.fixture(scope="module")
def semaforos(directorio_bin) -> Path:
    destino = directorio_bin / "semaforos"
    resultado = compilar("semaforos.c", destino, ("-O2",))
    assert resultado.returncode == 0, resultado.stderr
    return destino


def ejecutar(binario: Path, *argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(binario), *map(str, argumentos)],
        capture_output=True,
        text=True,
        timeout=TIEMPO_MAXIMO_S,
    )


# ---------------------------------------------------------------------------
# Traza: lectura y validadores
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evento:
    instante: int
    modulo: str
    entidad: str
    accion: str
    datos: dict[str, str]


def parsear_datos(texto: str) -> dict[str, str]:
    return dict(par.split("=", 1) for par in texto.split(";") if par)


def parsear_traza(salida: str) -> list[Evento]:
    lector = csv.DictReader(io.StringIO(salida))
    return [
        Evento(
            int(fila["instante"]),
            fila["modulo"],
            fila["entidad"],
            fila["accion"],
            parsear_datos(fila["datos"]),
        )
        for fila in lector
    ]


def resumen_de(eventos: list[Evento]) -> dict[str, str]:
    resumenes = [e for e in eventos if e.accion == "resumen"]
    assert len(resumenes) == 1, "la traza debe terminar con un unico resumen"
    assert eventos[-1] is resumenes[0]
    return resumenes[0].datos


def validar_exclusion(eventos: list[Evento]) -> list[str]:
    """Devuelve las violaciones de lectores-escritores que muestra la traza.

    Reglas: un escritor nunca comparte la seccion con otro escritor ni con
    lectores; los lectores si pueden compartirla entre si; todo inicio tiene su fin.
    """
    problemas: list[str] = []
    lectores: set[str] = set()
    escritor: str | None = None

    for e in eventos:
        if e.accion == "inicio_seccion":
            if e.entidad.startswith("E"):
                if escritor is not None:
                    problemas.append(f"{e.instante}: {e.entidad} entra con escritor {escritor}")
                if lectores:
                    problemas.append(f"{e.instante}: {e.entidad} entra con lectores {sorted(lectores)}")
                escritor = e.entidad
            else:
                if escritor is not None:
                    problemas.append(f"{e.instante}: {e.entidad} entra con escritor {escritor}")
                lectores.add(e.entidad)
        elif e.accion == "fin_seccion":
            if e.entidad == escritor:
                escritor = None
            elif e.entidad in lectores:
                lectores.discard(e.entidad)
            else:
                problemas.append(f"{e.instante}: {e.entidad} termina sin haber iniciado")

    if escritor is not None or lectores:
        problemas.append("la traza termina con secciones abiertas")
    return problemas


def concurrencia_maxima(eventos: list[Evento]) -> int:
    """Maximo de entidades simultaneamente dentro de su seccion, segun la traza."""
    dentro: set[str] = set()
    maximo = 0
    for e in eventos:
        if e.accion == "inicio_seccion":
            dentro.add(e.entidad)
            maximo = max(maximo, len(dentro))
        elif e.accion == "fin_seccion":
            dentro.discard(e.entidad)
    return maximo


def ciclo_por_entidad(eventos: list[Evento]) -> dict[str, list[str]]:
    ciclos: dict[str, list[str]] = {}
    for e in eventos:
        if e.accion != "resumen":
            ciclos.setdefault(e.entidad, []).append(e.accion)
    return ciclos


def escribir_escenario(ruta: Path, filas: list[str]) -> Path:
    ruta.write_text("id,tipo,llegada_ms,duracion_ms\n" + "\n".join(filas) + "\n", encoding="utf-8")
    return ruta


# ---------------------------------------------------------------------------
# Compilacion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fuente", ["lectores_escritores.c", "semaforos.c"])
def test_compila_sin_advertencias(fuente, directorio_bin):
    resultado = compilar(fuente, directorio_bin / f"warn_{fuente}", ("-O2",))
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stderr == "", f"advertencias del compilador:\n{resultado.stderr}"


# ---------------------------------------------------------------------------
# Validadores de traza (sin ejecutar C): comprueban que detectan errores
# ---------------------------------------------------------------------------

_BASE_VALIDA = """instante,modulo,entidad,accion,datos
1,sincronizacion,L1,inicio_seccion,x=1
2,sincronizacion,L2,inicio_seccion,x=2
3,sincronizacion,L1,fin_seccion,x=1
4,sincronizacion,L2,fin_seccion,x=2
5,sincronizacion,E3,inicio_seccion,x=3
6,sincronizacion,E3,fin_seccion,x=3
"""


def test_validador_acepta_traza_correcta():
    assert validar_exclusion(parsear_traza(_BASE_VALIDA)) == []
    assert concurrencia_maxima(parsear_traza(_BASE_VALIDA)) == 2


def test_validador_detecta_dos_escritores():
    traza = """instante,modulo,entidad,accion,datos
1,sincronizacion,E1,inicio_seccion,a=1
2,sincronizacion,E2,inicio_seccion,a=1
3,sincronizacion,E1,fin_seccion,a=1
4,sincronizacion,E2,fin_seccion,a=1
"""
    assert validar_exclusion(parsear_traza(traza))


def test_validador_detecta_lector_dentro_de_escritura():
    traza = """instante,modulo,entidad,accion,datos
1,sincronizacion,E1,inicio_seccion,a=1
2,sincronizacion,L2,inicio_seccion,a=1
3,sincronizacion,L2,fin_seccion,a=1
4,sincronizacion,E1,fin_seccion,a=1
"""
    assert validar_exclusion(parsear_traza(traza))


def test_validador_detecta_seccion_sin_cerrar():
    traza = """instante,modulo,entidad,accion,datos
1,sincronizacion,L1,inicio_seccion,a=1
"""
    assert validar_exclusion(parsear_traza(traza))


# ---------------------------------------------------------------------------
# lectores_escritores.c
# ---------------------------------------------------------------------------


def test_lectores_escritores_ejecucion_basica(lectores_escritores):
    resultado = ejecutar(lectores_escritores, "--orden", "LLELEEL", "--duracion-ms", "8")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    eventos = parsear_traza(resultado.stdout)
    resumen = resumen_de(eventos)
    assert resumen["operaciones"] == "7"
    assert resumen["lecturas"] == "4"
    assert resumen["escrituras"] == "3"
    assert resumen["version"] == "3"
    assert resumen["violaciones"] == "0"
    assert resumen["integridad"] == "ok"
    assert resumen["politica"] == "cola_servicio"


def test_traza_tiene_reloj_logico_consecutivo(lectores_escritores):
    eventos = parsear_traza(ejecutar(lectores_escritores, "--orden", "LELEL").stdout)
    assert [e.instante for e in eventos] == list(range(1, len(eventos) + 1))
    assert {e.modulo for e in eventos} == {"sincronizacion"}


def test_cada_operacion_sigue_llegada_inicio_fin(lectores_escritores):
    eventos = parsear_traza(ejecutar(lectores_escritores, "--orden", "LLEELLE").stdout)
    ciclos = ciclo_por_entidad(eventos)
    assert len(ciclos) == 7  # 7 operaciones; el resumen no cuenta
    for entidad, acciones in ciclos.items():
        if entidad == "sistema":
            continue
        assert acciones == ["llegada", "inicio_seccion", "fin_seccion"], entidad


def test_no_hay_escrituras_simultaneas_ni_lectores_con_escritor(lectores_escritores):
    resultado = ejecutar(
        lectores_escritores, "--orden", "LEELLEEELLELEE", "--duracion-ms", "6", "--intervalo-ms", "1"
    )
    assert resultado.returncode == 0, resultado.stdout
    eventos = parsear_traza(resultado.stdout)
    assert validar_exclusion(eventos) == []
    assert resumen_de(eventos)["violaciones"] == "0"


def test_solo_escritores_nunca_comparten_la_seccion(lectores_escritores):
    resultado = ejecutar(lectores_escritores, "--orden", "EEEEEE", "--duracion-ms", "10", "--intervalo-ms", "0")
    eventos = parsear_traza(resultado.stdout)
    assert resultado.returncode == 0
    assert concurrencia_maxima(eventos) == 1
    resumen = resumen_de(eventos)
    assert resumen["escrituras"] == "6"
    assert resumen["version"] == "6"


def test_lectores_consecutivos_comparten_el_padron(lectores_escritores):
    resultado = ejecutar(
        lectores_escritores, "--orden", "LLLL", "--duracion-ms", "120", "--intervalo-ms", "1"
    )
    eventos = parsear_traza(resultado.stdout)
    assert resultado.returncode == 0
    assert concurrencia_maxima(eventos) >= 2
    assert int(resumen_de(eventos)["max_lectores"]) >= 2


def test_escritor_en_espera_no_es_rebasado_por_lectores_tardios(lectores_escritores):
    """L1 ocupa el padron; E2 espera; L3 llega despues y debe entrar tras E2."""
    resultado = ejecutar(
        lectores_escritores, "--orden", "LEL", "--duracion-ms", "80", "--intervalo-ms", "15"
    )
    assert resultado.returncode == 0
    eventos = parsear_traza(resultado.stdout)
    inicios = [e.entidad for e in eventos if e.accion == "inicio_seccion"]
    assert inicios == ["L1", "E2", "L3"]


def test_escritor_aplica_matricula_y_conserva_cupos(lectores_escritores):
    """Cada curso mantiene cupos + matriculados == 30 al terminar."""
    resultado = ejecutar(lectores_escritores, "--orden", "EEEEEEEE", "--duracion-ms", "1", "--intervalo-ms", "0")
    resumen = resumen_de(parsear_traza(resultado.stdout))
    cursos = [par.split(":")[1].split("/") for par in resumen["padron"].split("|")]
    assert len(cursos) == 4
    for cupos, matriculados in cursos:
        assert int(cupos) + int(matriculados) == 30
    assert sum(int(m) for _, m in cursos) == 8


def test_cantidades_generan_orden_alternado(lectores_escritores):
    resultado = ejecutar(lectores_escritores, "--lectores", "3", "--escritores", "2", "--duracion-ms", "2")
    eventos = parsear_traza(resultado.stdout)
    llegadas = [e.entidad for e in eventos if e.accion == "llegada"]
    assert llegadas == ["L1", "E2", "L3", "E4", "L5"]
    assert resultado.returncode == 0


def test_escenario_csv_reproduce_el_mismo_resultado(lectores_escritores, tmp_path):
    ruta = escribir_escenario(
        tmp_path / "ops.csv",
        ["1,L,0,20", "2,E,5,15", "3,L,10,20", "4,L,12,20", "5,E,30,10", "6,L,35,10"],
    )
    primera = ejecutar(lectores_escritores, "--escenario", ruta)
    segunda = ejecutar(lectores_escritores, "--escenario", ruta)
    assert primera.returncode == 0 and segunda.returncode == 0

    clave = ("operaciones", "lecturas", "escrituras", "version", "padron", "violaciones", "integridad")
    resumen_a = resumen_de(parsear_traza(primera.stdout))
    resumen_b = resumen_de(parsear_traza(segunda.stdout))
    assert {k: resumen_a[k] for k in clave} == {k: resumen_b[k] for k in clave}

    llegadas_a = [e.entidad for e in parsear_traza(primera.stdout) if e.accion == "llegada"]
    llegadas_b = [e.entidad for e in parsear_traza(segunda.stdout) if e.accion == "llegada"]
    assert llegadas_a == llegadas_b == ["L1", "E2", "L3", "L4", "E5", "L6"]


def test_escenario_csv_ordena_por_llegada(lectores_escritores, tmp_path):
    ruta = escribir_escenario(tmp_path / "desordenado.csv", ["1,L,20,5", "2,E,0,5", "3,L,10,5"])
    eventos = parsear_traza(ejecutar(lectores_escritores, "--escenario", ruta).stdout)
    assert [e.entidad for e in eventos if e.accion == "llegada"] == ["E2", "L3", "L1"]


def test_escenario_csv_acepta_tres_columnas_y_comentarios(lectores_escritores, tmp_path):
    ruta = tmp_path / "corto.csv"
    ruta.write_text("# escenario de prueba\n1,lector,0\n2,escritor,1\n", encoding="utf-8")
    resultado = ejecutar(lectores_escritores, "--escenario", ruta, "--duracion-ms", "3")
    assert resultado.returncode == 0
    resumen = resumen_de(parsear_traza(resultado.stdout))
    assert (resumen["lecturas"], resumen["escrituras"]) == ("1", "1")


@pytest.mark.parametrize(
    "argumentos",
    [
        ("--orden", "LXE"),
        ("--orden", ""),
        ("--lectores", "-1"),
        ("--lectores", "abc"),
        ("--hilos", "3"),
        ("--orden", "LE", "--lectores", "2"),
        ("--escenario", "no_existe.csv"),
    ],
)
def test_argumentos_invalidos_terminan_con_codigo_2(lectores_escritores, argumentos):
    resultado = ejecutar(lectores_escritores, *argumentos)
    assert resultado.returncode == 2
    assert resultado.stderr != ""
    assert "resumen" not in resultado.stdout


def test_escenario_con_identificador_repetido_se_rechaza(lectores_escritores, tmp_path):
    ruta = escribir_escenario(tmp_path / "repetido.csv", ["1,L,0,5", "1,E,1,5"])
    resultado = ejecutar(lectores_escritores, "--escenario", ruta)
    assert resultado.returncode == 2
    assert "repetido" in resultado.stderr


def test_escenario_con_tipo_invalido_se_rechaza(lectores_escritores, tmp_path):
    ruta = escribir_escenario(tmp_path / "tipo.csv", ["1,Z,0,5"])
    resultado = ejecutar(lectores_escritores, "--escenario", ruta)
    assert resultado.returncode == 2
    assert "formato invalido" in resultado.stderr


def test_sin_sincronizacion_se_detecta_en_la_traza(lectores_escritores):
    """Control negativo: sin exclusion mutua el programa y el validador deben avisar."""
    resultado = ejecutar(
        lectores_escritores, "--orden", "LEEEL", "--duracion-ms", "40", "--intervalo-ms", "1", "--sin-sync"
    )
    assert resultado.returncode == 1
    eventos = parsear_traza(resultado.stdout)
    resumen = resumen_de(eventos)
    assert resumen["politica"] == "sin_sincronizacion"
    assert int(resumen["violaciones"]) > 0
    assert any(e.accion == "violacion" for e in eventos)
    assert validar_exclusion(eventos) != []


def test_repeticiones_con_carga_no_producen_violaciones(lectores_escritores):
    orden = "LLELEELLLELE" * 3
    for _ in range(5):
        resultado = ejecutar(
            lectores_escritores, "--orden", orden, "--duracion-ms", "2", "--intervalo-ms", "0"
        )
        eventos = parsear_traza(resultado.stdout)
        assert resultado.returncode == 0, resultado.stdout
        assert validar_exclusion(eventos) == []
        assert resumen_de(eventos)["integridad"] == "ok"


@pytest.mark.skipif(_compilador() is None, reason="No hay compilador C")
def test_sin_condiciones_de_carrera_segun_threadsanitizer(directorio_bin):
    destino = directorio_bin / "le_tsan"
    compilacion = compilar("lectores_escritores.c", destino, ("-O1", "-g", "-fsanitize=thread"))
    if compilacion.returncode != 0:
        pytest.skip("El compilador no soporta -fsanitize=thread aqui.")
    resultado = ejecutar(destino, "--orden", "LLELEEL", "--duracion-ms", "4", "--intervalo-ms", "1")
    if "unexpected memory mapping" in resultado.stderr or "FATAL: ThreadSanitizer" in resultado.stderr:
        pytest.skip("ThreadSanitizer no puede ejecutarse en este entorno.")
    assert "WARNING: ThreadSanitizer" not in resultado.stderr, resultado.stderr
    assert resultado.returncode == 0


# ---------------------------------------------------------------------------
# semaforos.c
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modo", ["mutex", "binario", "contador"])
def test_modos_protegidos_no_pierden_incrementos(semaforos, modo):
    resultado = ejecutar(
        semaforos, "--modo", modo, "--hilos", "8", "--iteraciones", "100", "--duracion-ms", "0"
    )
    assert resultado.returncode == 0, resultado.stdout
    resumen = resumen_de(parsear_traza(resultado.stdout))
    assert resumen["modo"] == modo
    assert resumen["esperado"] == resumen["final"] == "800"
    assert resumen["perdidas"] == "0"
    assert resumen["violaciones"] == "0"


@pytest.mark.parametrize("modo", ["mutex", "binario"])
def test_mutex_y_semaforo_binario_garantizan_exclusion_mutua(semaforos, modo):
    resultado = ejecutar(
        semaforos, "--modo", modo, "--hilos", "6", "--iteraciones", "4", "--duracion-ms", "2"
    )
    eventos = parsear_traza(resultado.stdout)
    assert resultado.returncode == 0
    assert concurrencia_maxima(eventos) == 1
    assert resumen_de(eventos)["max_en_zona"] == "1"


def test_semaforo_contador_limita_a_las_ventanillas(semaforos):
    resultado = ejecutar(
        semaforos,
        "--modo", "contador", "--hilos", "6", "--iteraciones", "3",
        "--ventanillas", "2", "--duracion-ms", "10",
    )  # fmt: skip
    eventos = parsear_traza(resultado.stdout)
    assert resultado.returncode == 0
    assert concurrencia_maxima(eventos) <= 2
    resumen = resumen_de(eventos)
    assert 1 <= int(resumen["max_en_zona"]) <= 2
    assert resumen["limite"] == "2"


def test_semaforo_contador_permite_concurrencia_real(semaforos):
    resultado = ejecutar(
        semaforos,
        "--modo", "contador", "--hilos", "4", "--iteraciones", "2",
        "--ventanillas", "3", "--duracion-ms", "40",
    )  # fmt: skip
    resumen = resumen_de(parsear_traza(resultado.stdout))
    assert int(resumen["max_en_zona"]) >= 2


def test_cada_seccion_registra_inicio_y_fin(semaforos):
    resultado = ejecutar(semaforos, "--modo", "mutex", "--hilos", "3", "--iteraciones", "2")
    eventos = [e for e in parsear_traza(resultado.stdout) if e.accion != "resumen"]
    assert sum(e.accion == "inicio_seccion" for e in eventos) == 6
    assert sum(e.accion == "fin_seccion" for e in eventos) == 6
    for entidad, acciones in ciclo_por_entidad(parsear_traza(resultado.stdout)).items():
        if entidad != "sistema":
            assert acciones == ["inicio_seccion", "fin_seccion"] * 2, entidad


def test_sin_sync_es_demostracion_y_no_falla(semaforos):
    resultado = ejecutar(
        semaforos, "--modo", "sin-sync", "--hilos", "8", "--iteraciones", "2000", "--duracion-ms", "0"
    )
    assert resultado.returncode == 0
    resumen = resumen_de(parsear_traza(resultado.stdout))
    esperado, final, perdidas = (int(resumen[k]) for k in ("esperado", "final", "perdidas"))
    assert esperado == 16000
    assert 0 < final <= esperado
    assert perdidas == esperado - final


def test_modo_todos_ejecuta_los_cuatro_modos(semaforos):
    resultado = ejecutar(semaforos, "--modo", "todos", "--hilos", "4", "--iteraciones", "50")
    assert resultado.returncode == 0
    resumenes = [
        parsear_datos(linea.split(",", 4)[4])
        for linea in resultado.stdout.splitlines()
        if ",resumen," in linea
    ]
    assert [r["modo"] for r in resumenes] == ["sin-sync", "mutex", "binario", "contador"]
    assert all(r["final"] == r["esperado"] for r in resumenes[1:])


@pytest.mark.parametrize(
    "argumentos",
    [
        ("--modo", "inexistente"),
        ("--hilos", "0"),
        ("--hilos", "1000"),
        ("--iteraciones", "-5"),
        ("--ventanillas", "0"),
        ("--duracion-ms", "x"),
        ("--desconocida", "1"),
        ("--hilos",),
    ],
)
def test_semaforos_argumentos_invalidos_terminan_con_codigo_2(semaforos, argumentos):
    resultado = ejecutar(semaforos, *argumentos)
    assert resultado.returncode == 2
    assert resultado.stderr != ""


@pytest.mark.skipif(_compilador() is None, reason="No hay compilador C")
def test_semaforos_sin_condiciones_de_carrera_en_modos_protegidos(directorio_bin):
    destino = directorio_bin / "sem_tsan"
    compilacion = compilar("semaforos.c", destino, ("-O1", "-g", "-fsanitize=thread"))
    if compilacion.returncode != 0:
        pytest.skip("El compilador no soporta -fsanitize=thread aqui.")
    for modo in ("mutex", "binario", "contador"):
        resultado = ejecutar(destino, "--modo", modo, "--hilos", "4", "--iteraciones", "20")
        if "unexpected memory mapping" in resultado.stderr or "FATAL: ThreadSanitizer" in resultado.stderr:
            pytest.skip("ThreadSanitizer no puede ejecutarse en este entorno.")
        assert "WARNING: ThreadSanitizer" not in resultado.stderr, f"{modo}: {resultado.stderr}"
        assert resultado.returncode == 0, modo