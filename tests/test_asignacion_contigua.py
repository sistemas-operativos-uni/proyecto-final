"""Pruebas de asignación y liberación de bloques contiguos.

Escritas con unittest para que funcionen con ``pytest`` y con
``python -m unittest`` sin dependencias.
"""

import unittest

from modulo4_memoria.py.asignacion_contigua import (
    ErrorMemoria,
    MemoriaContigua,
    SinEspacioError,
)


def memoria_con_dos_huecos(estrategia: str) -> MemoriaContigua:
    """Mapa [A 100 | libre 300 | B 100 | libre 100 | C 100 | libre 200] de 900 KB."""

    memoria = MemoriaContigua(900)
    for proceso, tamano in [("A", 100), ("X", 300), ("B", 100), ("Y", 100),
                            ("C", 100), ("Z", 200)]:
        memoria.asignar(proceso, tamano, estrategia)
    memoria.liberar("X")
    memoria.liberar("Y")
    memoria.liberar("Z")
    return memoria


class InvariantesMixin:
    def assert_mapa_valido(self, memoria: MemoriaContigua) -> None:
        bloques = memoria.bloques
        self.assertEqual(bloques[0].inicio_kb, 0)
        self.assertEqual(bloques[-1].fin_kb, memoria.total_kb)
        for anterior, siguiente in zip(bloques, bloques[1:]):
            self.assertEqual(anterior.fin_kb, siguiente.inicio_kb, "bloques no contiguos")
            self.assertFalse(anterior.libre and siguiente.libre, "huecos sin fusionar")


class AsignacionTests(InvariantesMixin, unittest.TestCase):
    def test_la_memoria_empieza_como_un_solo_hueco(self):
        memoria = MemoriaContigua(512)

        self.assertEqual(len(memoria.bloques), 1)
        self.assertTrue(memoria.bloques[0].libre)
        self.assertEqual(memoria.bloques[0].tamano_kb, 512)

    def test_asignar_parte_el_hueco_y_deja_el_resto_libre(self):
        memoria = MemoriaContigua(512)

        bloque = memoria.asignar("P001", 128, "primer")

        self.assertEqual((bloque.inicio_kb, bloque.fin_kb), (0, 128))
        self.assertEqual([(b.proceso_id, b.tamano_kb) for b in memoria.bloques],
                         [("P001", 128), (None, 384)])
        self.assert_mapa_valido(memoria)

    def test_redondea_a_la_unidad_de_asignacion(self):
        memoria = MemoriaContigua(512, unidad_kb=64)

        bloque = memoria.asignar("P002", 96, "primer")

        self.assertEqual(bloque.tamano_kb, 128)
        self.assertEqual(bloque.solicitado_kb, 96)
        self.assertEqual(bloque.desperdicio_kb, 32)

    def test_primer_ajuste_elige_el_primer_hueco_suficiente(self):
        memoria = memoria_con_dos_huecos("primer")

        self.assertEqual(memoria.asignar("P", 100, "primer").inicio_kb, 100)

    def test_mejor_ajuste_elige_el_hueco_mas_pequeno_suficiente(self):
        memoria = memoria_con_dos_huecos("mejor")

        self.assertEqual(memoria.asignar("P", 100, "mejor").inicio_kb, 500)

    def test_peor_ajuste_elige_el_hueco_mas_grande(self):
        memoria = memoria_con_dos_huecos("peor")

        self.assertEqual(memoria.asignar("P", 100, "peor").inicio_kb, 100)

    def test_peor_ajuste_y_primer_ajuste_pueden_diferir(self):
        memoria = memoria_con_dos_huecos("peor")
        memoria.asignar("Q", 250, "peor")  # el hueco de 300 queda en 50

        self.assertEqual(memoria.asignar("P", 100, "peor").inicio_kb, 700)

    def test_rechaza_un_proceso_que_ya_tiene_bloque(self):
        memoria = MemoriaContigua(512)
        memoria.asignar("P001", 64, "primer")

        with self.assertRaises(ErrorMemoria):
            memoria.asignar("P001", 64, "primer")

    def test_sin_espacio_por_falta_de_memoria(self):
        memoria = MemoriaContigua(256)
        memoria.asignar("P001", 200, "primer")

        with self.assertRaises(SinEspacioError) as contexto:
            memoria.asignar("P002", 100, "primer")

        self.assertFalse(contexto.exception.por_fragmentacion)

    def test_sin_espacio_por_fragmentacion_externa(self):
        memoria = memoria_con_dos_huecos("primer")
        # Libres: 300 + 100 + 200 = 600 KB, pero el hueco mayor es de 300.

        with self.assertRaises(SinEspacioError) as contexto:
            memoria.asignar("P", 400, "primer")

        self.assertTrue(contexto.exception.por_fragmentacion)
        self.assertEqual(contexto.exception.libre_total_kb, 600)
        self.assertEqual(contexto.exception.hueco_mayor_kb, 300)

    def test_valida_parametros(self):
        with self.assertRaises(ValueError):
            MemoriaContigua(500, unidad_kb=64)
        with self.assertRaises(ValueError):
            MemoriaContigua(512).asignar("P", 0, "primer")
        with self.assertRaises(ValueError):
            MemoriaContigua(512).asignar("P", 64, "siguiente")


class LiberacionTests(InvariantesMixin, unittest.TestCase):
    def test_liberar_fusiona_con_los_dos_vecinos(self):
        memoria = MemoriaContigua(300)
        for proceso in ("A", "B", "C"):
            memoria.asignar(proceso, 100, "primer")
        memoria.liberar("A")
        memoria.liberar("C")

        memoria.liberar("B")

        self.assertEqual(len(memoria.bloques), 1)
        self.assertTrue(memoria.bloques[0].libre)
        self.assert_mapa_valido(memoria)

    def test_liberar_sin_vecinos_libres_no_fusiona(self):
        memoria = MemoriaContigua(300)
        for proceso in ("A", "B", "C"):
            memoria.asignar(proceso, 100, "primer")

        memoria.liberar("B")

        self.assertEqual([b.proceso_id for b in memoria.bloques], ["A", None, "C"])

    def test_liberar_un_proceso_sin_memoria_es_error(self):
        with self.assertRaises(ErrorMemoria):
            MemoriaContigua(512).liberar("P999")

    def test_el_mapa_sigue_valido_tras_muchas_operaciones(self):
        for estrategia in ("primer", "mejor", "peor"):
            with self.subTest(estrategia=estrategia):
                memoria = MemoriaContigua(1024, unidad_kb=32)
                for i in range(12):
                    try:
                        memoria.asignar(f"P{i}", 40 + 17 * i, estrategia)
                    except SinEspacioError:
                        pass
                    anterior = f"P{i - 1}"
                    if i % 3 == 2 and memoria.bloque_de(anterior) is not None:
                        memoria.liberar(anterior)
                    self.assert_mapa_valido(memoria)


if __name__ == "__main__":
    unittest.main()
