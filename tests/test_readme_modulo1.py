"""El README y la guía de instalación deben describir el Módulo 1 tal como está.

Un README con un comando que ya no existe, o que sigue diciendo "esqueleto"
sobre código implementado, engaña a quien lo lee. Estas pruebas ejecutan los
comandos que el README documenta y rechazan el texto desactualizado.
"""

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
README = RAIZ / "README.md"
INSTALACION = RAIZ / "docs" / "instalacion_y_ejecucion.md"

# Comandos del módulo que sí se ejecutan. `make` se prueba en modo simulado
# (-n): comprueba que el objetivo existe sin repetir trabajo que otras pruebas ya hacen.
PREFIJOS_EJECUTABLES = ("python main.py", "python -m modulo1_procesos")
OBJETIVOS_RAIZ = ("cargar", "procesos", "procesos-c", "planificacion", "comparacion", "test")
OBJETIVOS_C = ("all", "sanitize", "werror", "hilos-tsan", "run-procesos", "run-hilos")


@pytest.fixture(scope="module")
def readme():
    return README.read_text(encoding="utf-8")


def comandos_de(texto):
    """Líneas de los bloques ```bash del documento."""
    lineas = []
    for bloque in re.findall(r"```bash\n(.*?)```", texto, flags=re.S):
        lineas += [l.strip() for l in bloque.splitlines() if l.strip() and not l.strip().startswith("#")]
    return lineas


def test_el_readme_declara_cerrado_el_modulo_1(readme):
    assert re.search(r"M[óo]dulo 1.*cerrado", readme, flags=re.I)


def test_el_readme_ya_no_dice_que_el_codigo_son_esqueletos(readme):
    for obsoleto in ("esqueletos comentados", "todavía no implementan", "Estado inicial", "será el punto de entrada"):
        assert obsoleto not in readme, obsoleto


def test_el_readme_tiene_una_tabla_de_estado_con_los_siete_modulos(readme):
    estado = readme[readme.index("## Estado del proyecto"):]
    for numero in range(1, 8):
        assert re.search(rf"\|\s*{numero}\s*\|", estado), f"falta la fila del módulo {numero}"


def test_el_readme_documenta_los_objetivos_de_make_del_modulo(readme):
    for objetivo in ("procesos", "procesos-c", "planificacion", "comparacion", "sanitize", "werror"):
        assert objetivo in readme, objetivo


def test_el_readme_enlaza_la_documentacion_del_modulo(readme):
    assert "modulo1_procesos/docs/WORKPLAN.md" in readme
    assert "modulo1_procesos/docs/IMPLEMENTATIONS.md" in readme


def test_el_readme_avisa_de_las_fallas_conocidas_del_modulo_2(readme):
    assert "Problemas conocidos" in readme and "semaphore.h" in readme


def test_hay_comandos_que_comprobar(readme):
    assert len([c for c in comandos_de(readme) if c.startswith(("make ", *PREFIJOS_EJECUTABLES))]) >= 6


def test_cada_comando_make_del_readme_existe(readme):
    comandos = [c for c in comandos_de(readme) if c.startswith("make ")]
    for comando in comandos:
        argumentos = shlex.split(comando, comments=True)[1:]
        r = subprocess.run(["make", "-n", *argumentos], cwd=RAIZ, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, f"{comando}\n{r.stderr}"


def test_cada_comando_python_del_readme_funciona(readme):
    comandos = [c for c in comandos_de(readme) if c.startswith(PREFIJOS_EJECUTABLES)]
    assert comandos
    for comando in comandos:
        if "--exportar" in comando:
            continue  # escribiría en resultados/; la exportación ya tiene sus propias pruebas
        argumentos = shlex.split(comando, comments=True)
        r = subprocess.run([sys.executable, *argumentos[1:]], cwd=RAIZ, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, f"{comando}\n{r.stderr}"


@pytest.mark.parametrize("objetivo", OBJETIVOS_RAIZ)
def test_los_objetivos_del_makefile_raiz_estan_en_la_guia(objetivo):
    assert f"make {objetivo}" in INSTALACION.read_text(encoding="utf-8") or f"`{objetivo}`" in INSTALACION.read_text(encoding="utf-8")


@pytest.mark.parametrize("objetivo", OBJETIVOS_C)
def test_los_objetivos_del_makefile_de_c_estan_en_la_guia(objetivo):
    assert objetivo in INSTALACION.read_text(encoding="utf-8")


def test_la_guia_ya_no_dice_que_los_comandos_estan_por_añadir():
    texto = INSTALACION.read_text(encoding="utf-8")
    assert "parten como comentarios de diseño" not in texto
    assert "El equipo añadirá los comandos" not in texto


def test_la_guia_menciona_las_herramientas_opcionales():
    texto = INSTALACION.read_text(encoding="utf-8")
    for herramienta in ("matplotlib", "valgrind", "pytest"):
        assert herramienta in texto, herramienta
