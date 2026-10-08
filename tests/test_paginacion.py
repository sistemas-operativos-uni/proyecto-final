# Pruebas pendientes para traducción de direcciones y tablas de páginas.

import pytest

from modulo3_paginacion.py.paginacion import (
    dividir_direccion_logica,
    traducir_direccion,
)

def test_dividir_direccion_logica() -> None:
    assert dividir_direccion_logica(600, 256) == (2, 88)

def test_traducir_direccion() -> None:
    assert traducir_direccion(600, 256, {2: 5}) == 1368

def test_direccion_logica_negativa() -> None:
    with pytest.raises(ValueError):
        dividir_direccion_logica(-1, 256)

def test_tamano_pagina_invalido() -> None:
    with pytest.raises(ValueError):
        dividir_direccion_logica(100, 0)

def test_pagina_no_presente_en_tabla() -> None:
    with pytest.raises(KeyError):
        traducir_direccion(600, 256, {1: 5})