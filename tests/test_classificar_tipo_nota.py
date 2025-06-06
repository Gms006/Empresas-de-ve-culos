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
def test_cfop_priority(cfop, expected):
    assert classificar_tipo_nota(CNPJ, "00000000000000", CNPJ, cfop) == expected


def test_cnpj_fallback_entrada():
    assert classificar_tipo_nota("123", CNPJ, CNPJ, None) == "Entrada"


def test_cnpj_fallback_saida():
    assert classificar_tipo_nota(CNPJ, "123", CNPJ, None) == "Saída"


def test_cnpj_fallback_indefinido():
    assert classificar_tipo_nota("123", "456", CNPJ, None) == "Indefinido"
