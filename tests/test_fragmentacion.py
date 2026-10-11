"""Pruebas de fragmentación interna y externa."""

import unittest

from modulo4_memoria.py.asignacion_contigua import Bloque, MemoriaContigua
from modulo4_memoria.py.fragmentacion import (
    fragmentacion_externa,
    fragmentacion_interna,
    medir,
)


class FragmentacionInternaTests(unittest.TestCase):
    def test_sin_redondeo_no_hay_fragmentacion_interna(self):
        memoria = MemoriaContigua(512, unidad_kb=1)
        memoria.asignar("P002", 96, "primer")

        interna = fragmentacion_interna(memoria.bloques)

        self.assertEqual(interna.desperdicio_kb, 0)
        self.assertEqual(interna.porcentaje, 0.0)

    def test_suma_el_desperdicio_de_cada_bloque(self):
        memoria = MemoriaContigua(512, unidad_kb=64)
        memoria.asignar("P002", 96, "primer")   # 128 asignados, 32 de sobra
        memoria.asignar("P003", 160, "primer")  # 192 asignados, 32 de sobra

        interna = fragmentacion_interna(memoria.bloques)

        self.assertEqual(interna.asignado_kb, 320)
        self.assertEqual(interna.solicitado_kb, 256)
        self.assertEqual(interna.desperdicio_kb, 64)
        self.assertEqual(interna.porcentaje, 20.0)

    def test_los_huecos_no_cuentan_como_fragmentacion_interna(self):
        interna = fragmentacion_interna([Bloque(0, 512)])

        self.assertEqual((interna.asignado_kb, interna.desperdicio_kb), (0, 0))
        self.assertEqual(interna.porcentaje, 0.0)


class FragmentacionExternaTests(unittest.TestCase):
    def test_un_solo_hueco_es_cero_por_ciento(self):
        externa = fragmentacion_externa([Bloque(0, 128, "P001", 128), Bloque(128, 384)])

        self.assertEqual(externa.cantidad_huecos, 1)
        self.assertEqual(externa.porcentaje, 0.0)

    def test_dos_huecos_iguales_es_cincuenta_por_ciento(self):
        bloques = [Bloque(0, 64), Bloque(64, 64, "P004", 64), Bloque(128, 64)]

        externa = fragmentacion_externa(bloques)

        self.assertEqual(externa.libre_total_kb, 128)
        self.assertEqual(externa.hueco_mayor_kb, 64)
        self.assertEqual(externa.porcentaje, 50.0)

    def test_memoria_llena_no_tiene_fragmentacion_externa(self):
        externa = fragmentacion_externa([Bloque(0, 512, "P001", 512)])

        self.assertEqual((externa.libre_total_kb, externa.cantidad_huecos), (0, 0))
        self.assertEqual(externa.porcentaje, 0.0)

    def test_el_reporte_combina_ambas_medidas(self):
        bloques = [Bloque(0, 128, "P002", 96), Bloque(128, 64), Bloque(192, 64, "X", 64),
                   Bloque(256, 128)]

        reporte = medir(bloques).como_diccionario()

        self.assertEqual(reporte["fragmentacion_interna_kb"], 32)
        self.assertEqual(reporte["libre_total_kb"], 192)
        self.assertEqual(reporte["hueco_mayor_kb"], 128)
        self.assertEqual(reporte["fragmentacion_externa_pct"], 33.33)


if __name__ == "__main__":
    unittest.main()
