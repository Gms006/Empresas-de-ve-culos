import os
import sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from modules.estoque_veiculos import classificar_tipo_nota

CNPJ = "41492247000150"

@pytest.mark.parametrize("cfop,expected",[
    ("1102","Entrada"),
    ("2102","Entrada"),
    ("5102","Saída"),
    ("6102","Saída"),
    ("9999","Indefinido"),
])
def test_cfop_aplicado_quando_ambos_sao_empresa(cfop, expected):
    assert classificar_tipo_nota(CNPJ, CNPJ, CNPJ, cfop) == expected


def test_cnpj_regra_entrada():
    assert classificar_tipo_nota("123", CNPJ, CNPJ, "5102") == "Entrada"


def test_cnpj_regra_saida():
    assert classificar_tipo_nota(CNPJ, "123", CNPJ, "1102") == "Saída"


def test_cnpj_regra_indefinido():
    assert classificar_tipo_nota("123", "456", CNPJ, "1102") == "Indefinido"
