"""Pruebas del gestor de memoria sobre el escenario del repositorio."""

import tempfile
import unittest
from pathlib import Path

from modulo4_memoria.py.gestor_memoria import (
    GestorMemoria,
    Solicitud,
    cargar_solicitudes,
    comparar_estrategias,
)

RAIZ = Path(__file__).resolve().parents[1]
ESCENARIO = RAIZ / "escenarios" / "solicitudes_memoria.csv"


class CargaEscenarioTests(unittest.TestCase):
    def test_carga_las_ocho_solicitudes_del_escenario(self):
        solicitudes = cargar_solicitudes(ESCENARIO)

        self.assertEqual(len(solicitudes), 8)
        self.assertEqual(solicitudes[0], Solicitud(1, "P001", "asignar", 128))
        self.assertEqual(solicitudes[3], Solicitud(4, "P002", "liberar", 96))

    def test_rechaza_operaciones_desconocidas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "malo.csv"
            ruta.write_text("paso,proceso_id,operacion,tamano_kb\n1,P1,compactar,64\n",
                            encoding="utf-8")

            with self.assertRaises(ValueError):
                cargar_solicitudes(ruta)


class GestorEscenarioTests(unittest.TestCase):
    def setUp(self):
        self.solicitudes = cargar_solicitudes(ESCENARIO)

    def test_las_tres_estrategias_completan_el_escenario(self):
        for estrategia, resultado in comparar_estrategias(self.solicitudes).items():
            with self.subTest(estrategia=estrategia):
                self.assertEqual(resultado.estado, "completado")
                self.assertEqual(resultado.errores, ())
                self.assertEqual(resultado.metricas["asignaciones"], 4)
                self.assertEqual(resultado.metricas["liberaciones"], 4)

    def test_al_final_la_memoria_vuelve_a_ser_un_solo_hueco(self):
        resultado = GestorMemoria(estrategia="primer").ejecutar(self.solicitudes)

        self.assertEqual(len(resultado.mapa_final), 1)
        self.assertTrue(resultado.mapa_final[0].libre)
        self.assertEqual(resultado.metricas["final_libre_total_kb"], 512)

    def test_el_paso_5_muestra_la_diferencia_entre_estrategias(self):
        resultados = comparar_estrategias(self.solicitudes)
        paso5 = {nombre: r.eventos[4] for nombre, r in resultados.items()}

        self.assertEqual(paso5["primer"].datos["inicio_kb"], 128)
        self.assertEqual(paso5["mejor"].datos["inicio_kb"], 448)
        self.assertEqual(paso5["peor"].datos["inicio_kb"], 128)
        self.assertEqual(
            paso5["primer"].datos["fragmentacion"]["fragmentacion_externa_pct"], 50.0)
        self.assertEqual(
            paso5["mejor"].datos["fragmentacion"]["fragmentacion_externa_pct"], 0.0)

    def test_la_fragmentacion_interna_maxima_es_64_kb(self):
        # 96 -> 128 y 160 -> 192 con unidad de 64 KB: 32 + 32 KB de sobra.
        resultado = GestorMemoria(estrategia="mejor").ejecutar(self.solicitudes)

        self.assertEqual(resultado.metricas["max_fragmentacion_interna_kb"], 64)

    def test_registra_un_evento_por_paso_con_mapa(self):
        resultado = GestorMemoria(estrategia="primer").ejecutar(self.solicitudes)

        self.assertEqual([e.instante for e in resultado.eventos], list(range(1, 9)))
        self.assertTrue(all(e.modulo == "memoria" for e in resultado.eventos))
        self.assertEqual(resultado.eventos[0].datos["mapa"], "[P001 128 | libre 384]")


class ErroresRecuperablesTests(unittest.TestCase):
    def test_un_rechazo_por_fragmentacion_no_detiene_la_simulacion(self):
        solicitudes = cargar_solicitudes(ESCENARIO)[:5] + [
            Solicitud(6, "P005", "asignar", 128),  # hay 128 KB libres, en dos huecos
            Solicitud(7, "P006", "asignar", 64),
        ]

        resultado = GestorMemoria(estrategia="primer").ejecutar(solicitudes)

        self.assertEqual(resultado.estado, "completado_con_errores")
        self.assertEqual(resultado.eventos[5].accion, "rechazado")
        self.assertTrue(resultado.eventos[5].datos["por_fragmentacion"])
        self.assertEqual(resultado.eventos[6].accion, "asignado")
        self.assertEqual(resultado.metricas["rechazos_por_fragmentacion"], 1)

    def test_el_mejor_ajuste_si_atiende_esa_misma_solicitud(self):
        solicitudes = cargar_solicitudes(ESCENARIO)[:5] + [
            Solicitud(6, "P005", "asignar", 128),
        ]

        resultado = GestorMemoria(estrategia="mejor").ejecutar(solicitudes)

        self.assertEqual(resultado.estado, "completado")
        self.assertEqual(resultado.eventos[5].accion, "asignado")

    def test_liberar_con_tamano_distinto_se_registra_y_no_libera(self):
        solicitudes = [Solicitud(1, "P001", "asignar", 128),
                       Solicitud(2, "P001", "liberar", 64)]

        resultado = GestorMemoria(estrategia="primer").ejecutar(solicitudes)

        self.assertEqual(resultado.eventos[1].accion, "error")
        self.assertEqual(resultado.mapa_final[0].proceso_id, "P001")

    def test_liberar_un_proceso_desconocido_es_error_recuperable(self):
        resultado = GestorMemoria().ejecutar([Solicitud(1, "P999", "liberar", 64)])

        self.assertEqual(resultado.estado, "completado_con_errores")
        self.assertIn("P999", resultado.errores[0])


if __name__ == "__main__":
    unittest.main()
