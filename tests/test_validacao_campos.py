import pandas as pd
import pytest
from utils.validacao_utils import validar_campos_obrigatorios


def _base_df():
    return pd.DataFrame(
        {
            "Tipo Nota": ["Entrada"],
            "Chassi": ["ABC"],
            "Placa": ["AAA1234"],
            "CFOP": ["5102"],
            "Valor Total": [1000],
            "Data Emissão": ["2023-01-01"],
        }
    )


def test_validar_campos_obrigatorios_ok():
    df = _base_df()
    validar_campos_obrigatorios(df)  # não deve lançar


def test_validar_campos_obrigatorios_coluna_ausente(caplog):
    df = _base_df().drop(columns=["CFOP"])
    with pytest.raises(ValueError):
        validar_campos_obrigatorios(df)
    assert "CFOP" in caplog.text


def test_validar_campos_obrigatorios_valor_vazio(caplog):
    df = _base_df()
    df.loc[0, "Chassi"] = None
    with pytest.raises(ValueError):
        validar_campos_obrigatorios(df)
    assert "Chassi" in caplog.text
