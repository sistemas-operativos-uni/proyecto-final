"""Pruebas del gráfico de barras de la comparación (Fase 6 del Módulo 1).

El gráfico muestra la espera media y el retorno medio de cada algoritmo. Se
dibuja con el backend Agg, que escribe a un búfer en memoria y no necesita
pantalla; las pruebas lo comprueban en un proceso limpio con un backend de
ventana pedido por entorno, que fallaría sin `DISPLAY`.
"""

import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from core.cargador_escenarios import cargar_procesos  # noqa: E402
from modulo1_procesos.py.graficos import construir_figura, graficar_comparacion  # noqa: E402
from modulo1_procesos.py.metricas_planificacion import comparar_algoritmos  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
NOMBRES = ["FCFS", "SJF", "PRIORIDAD", "RR(q=2)"]


def lote_pequeno():
    return cargar_procesos(RAIZ / "escenarios" / "lote_pequeno.csv")


def lote_grande():
    return cargar_procesos(RAIZ / "escenarios" / "lote_grande.csv")


def dimensiones_png(ruta):
    cabecera = ruta.read_bytes()[:24]
    return struct.unpack(">II", cabecera[16:24])  # ancho y alto del bloque IHDR


# --- Contenido de la figura -------------------------------------------------


def test_la_figura_tiene_dos_series_de_barras_con_las_medias_de_cada_algoritmo():
    ax = construir_figura(comparar_algoritmos(lote_pequeno()), "lote_pequeno.csv").axes[0]
    assert [c.get_label() for c in ax.containers] == ["Espera media", "Retorno medio"]
    alturas = [[barra.get_height() for barra in c] for c in ax.containers]
    assert alturas == [[5.25, 3.75, 4.0, 7.0], [9.5, 8.0, 8.25, 11.25]]


def test_el_eje_x_nombra_los_algoritmos_en_el_orden_del_registro():
    ax = construir_figura(comparar_algoritmos(lote_pequeno())).axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == NOMBRES


def test_cada_barra_muestra_su_valor():
    ax = construir_figura(comparar_algoritmos(lote_pequeno())).axes[0]
    assert sorted(t.get_text() for t in ax.texts) == sorted(
        ["5.25", "3.75", "4.00", "7.00", "9.50", "8.00", "8.25", "11.25"]
    )


def test_el_titulo_nombra_el_escenario_y_el_eje_y_la_unidad():
    ax = construir_figura(comparar_algoritmos(lote_pequeno()), "lote_pequeno.csv").axes[0]
    assert "lote_pequeno.csv" in ax.get_title()
    assert ax.get_ylabel() == "Unidades de tiempo"
    assert ax.get_legend() is not None


def test_sin_escenario_el_titulo_no_queda_con_un_hueco():
    ax = construir_figura(comparar_algoritmos(lote_pequeno())).axes[0]
    assert "None" not in ax.get_title() and "|" not in ax.get_title()


def test_con_lote_grande_las_alturas_coinciden_con_las_metricas():
    comparacion = comparar_algoritmos(lote_grande())
    ax = construir_figura(comparacion, "lote_grande.csv").axes[0]
    esperas = [m.espera_media for m in comparacion.metricas]
    assert [b.get_height() for b in ax.containers[0]] == esperas
    assert max(b.get_height() for b in ax.containers[1]) > max(esperas)  # el retorno incluye la ráfaga


def test_sin_datos_que_graficar_es_un_error_y_no_deja_un_grafico_vacio(tmp_path):
    vacia = comparar_algoritmos([])
    with pytest.raises(ValueError, match="graficar"):
        construir_figura(vacia)
    with pytest.raises(ValueError):
        graficar_comparacion(vacia, "vacio", tmp_path)
    assert list(tmp_path.iterdir()) == []


# --- Archivo PNG ------------------------------------------------------------


def test_graficar_escribe_el_png_con_el_nombre_del_escenario(tmp_path):
    ruta = graficar_comparacion(comparar_algoritmos(lote_pequeno()), "escenarios/lote_pequeno.csv", tmp_path)
    assert ruta == tmp_path / "procesos_lote_pequeno.png"
    assert ruta.read_bytes().startswith(FIRMA_PNG)


def test_el_png_tiene_el_tamano_fijo_de_la_figura(tmp_path):
    ruta = graficar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno", tmp_path)
    assert dimensiones_png(ruta) == (800, 450)
    assert ruta.stat().st_size > 5_000  # un PNG con barras y texto, no uno en blanco


def test_graficar_crea_los_directorios_que_falten(tmp_path):
    destino = tmp_path / "a" / "b"
    ruta = graficar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno", destino)
    assert ruta.parent == destino and ruta.is_file()


def test_graficar_dos_veces_da_los_mismos_bytes(tmp_path):
    comparacion = comparar_algoritmos(lote_pequeno())
    primero = graficar_comparacion(comparacion, "lote_pequeno", tmp_path).read_bytes()
    segundo = graficar_comparacion(comparacion, "lote_pequeno", tmp_path).read_bytes()
    assert primero == segundo  # sin marcas de versión ni fecha en el archivo


def test_graficar_reemplaza_un_archivo_anterior(tmp_path):
    (tmp_path / "procesos_lote_pequeno.png").write_bytes(b"viejo")
    ruta = graficar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno", tmp_path)
    assert ruta.read_bytes().startswith(FIRMA_PNG)


def test_graficar_en_una_ruta_que_es_un_archivo_lanza_os_error(tmp_path):
    archivo = tmp_path / "no_es_carpeta"
    archivo.write_text("x", encoding="utf-8")
    with pytest.raises(OSError):
        graficar_comparacion(comparar_algoritmos(lote_pequeno()), "lote_pequeno", archivo)


# --- Backend Agg sin pantalla ------------------------------------------------


def test_funciona_sin_pantalla_aunque_el_entorno_pida_un_backend_de_ventana(tmp_path):
    codigo = (
        "import sys\n"
        "from pathlib import Path\n"
        "from core.cargador_escenarios import cargar_procesos\n"
        "from modulo1_procesos.py.graficos import graficar_comparacion\n"
        "from modulo1_procesos.py.metricas_planificacion import comparar_algoritmos\n"
        f"c = comparar_algoritmos(cargar_procesos('escenarios/lote_pequeno.csv'))\n"
        f"print(graficar_comparacion(c, 'lote_pequeno', Path(r'{tmp_path}')))\n"
        "print('pyplot' if 'matplotlib.pyplot' in sys.modules else 'sin pyplot')\n"
    )
    entorno = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    entorno["MPLBACKEND"] = "TkAgg"  # fallaría sin pantalla si se usara pyplot
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=entorno, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[-1] == "sin pyplot"
    assert (tmp_path / "procesos_lote_pequeno.png").is_file()


def test_importar_el_modulo_no_carga_matplotlib():
    # matplotlib se importa al graficar, no al arrancar: el resto del módulo
    # sigue funcionando en una máquina que no lo tenga.
    codigo = "import sys, modulo1_procesos.py.graficos; print('matplotlib' in sys.modules)"
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False"
