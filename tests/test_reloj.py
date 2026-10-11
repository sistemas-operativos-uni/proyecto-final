"""Pruebas del reloj lógico compartido."""

import pytest

from core.reloj import RelojLogico


def test_inicio_por_defecto_es_cero():
    assert RelojLogico().ahora == 0


def test_inicio_personalizado():
    assert RelojLogico(inicio=7).ahora == 7


@pytest.mark.parametrize("inicio", [-1, True, 1.5, "0", None])
def test_inicio_invalido_lanza_valueerror(inicio):
    with pytest.raises(ValueError):
        RelojLogico(inicio=inicio)


def test_avanzar_por_defecto_suma_una_unidad():
    reloj = RelojLogico()
    assert reloj.avanzar() == 1
    assert reloj.ahora == 1


def test_avanzar_acumula_unidades():
    reloj = RelojLogico()
    reloj.avanzar(3)
    assert reloj.avanzar(4) == 7
    assert reloj.ahora == 7


def test_avanzar_cero_deja_el_reloj_igual():
    reloj = RelojLogico(inicio=5)
    assert reloj.avanzar(0) == 5
    assert reloj.ahora == 5


def test_avanzar_negativo_lanza_valueerror_y_no_muta():
    reloj = RelojLogico(inicio=5)
    with pytest.raises(ValueError):
        reloj.avanzar(-1)
    assert reloj.ahora == 5


@pytest.mark.parametrize("unidades", [True, 1.5, "2", None])
def test_avanzar_tipo_invalido_lanza_valueerror(unidades):
    reloj = RelojLogico()
    with pytest.raises(ValueError):
        reloj.avanzar(unidades)
    assert reloj.ahora == 0


def test_saltar_adelante_devuelve_y_fija_el_instante():
    reloj = RelojLogico(inicio=2)
    assert reloj.saltar_a(10) == 10
    assert reloj.ahora == 10


def test_saltar_al_mismo_instante_esta_permitido():
    reloj = RelojLogico(inicio=4)
    assert reloj.saltar_a(4) == 4
    assert reloj.ahora == 4


def test_saltar_atras_lanza_valueerror_y_deja_el_reloj_intacto():
    reloj = RelojLogico(inicio=10)
    with pytest.raises(ValueError):
        reloj.saltar_a(9)
    assert reloj.ahora == 10


@pytest.mark.parametrize("instante", [True, 12.0, "12", None])
def test_saltar_tipo_invalido_lanza_valueerror_y_no_muta(instante):
    reloj = RelojLogico(inicio=3)
    with pytest.raises(ValueError):
        reloj.saltar_a(instante)
    assert reloj.ahora == 3


def test_ahora_no_se_puede_asignar():
    reloj = RelojLogico()
    with pytest.raises(AttributeError):
        reloj.ahora = 5
