import os
import sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from modules.estoque_veiculos import classificar_tipo_nota

CNPJ = "41492247000150"

@pytest.mark.parametrize("cfop", ["1102", "2102", "5102", "6102", "9999"])
def test_destinatario_prioritario_quando_ambos_sao_empresa(cfop):
    assert classificar_tipo_nota(CNPJ, CNPJ, CNPJ, cfop) == "Entrada"


def test_cnpj_regra_entrada():
    assert classificar_tipo_nota("123", CNPJ, CNPJ, "5102") == "Entrada"


def test_cnpj_regra_saida():
    assert classificar_tipo_nota(CNPJ, "123", CNPJ, "5102") == "Saída"


def test_emitente_indefinido_por_cfop():
    assert classificar_tipo_nota(CNPJ, "123", CNPJ, "1102") == "Entrada"


def test_alerta_emitida_pela_empresa():
    tipo, alerta = classificar_tipo_nota(CNPJ, "123", CNPJ, "1102", retornar_alerta=True)
    assert tipo == "Entrada"
    assert alerta.startswith("Entrada emitida")


def test_cnpj_regra_indefinido():
    tipo, alerta = classificar_tipo_nota("123", "456", CNPJ, "1102", retornar_alerta=True)
    assert tipo == "Indefinido"
    assert alerta.startswith("Nota não envolve")
