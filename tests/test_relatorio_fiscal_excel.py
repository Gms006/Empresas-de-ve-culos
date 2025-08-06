import pandas as pd
from modules.relatorio_fiscal_excel import gerar_relatorio_fiscal_excel


def test_gerar_relatorio_fiscal_excel(tmp_path):
    df = pd.DataFrame(
        {
            "CPF/CNPJ": ["99.999.999/0001-01"],
            "Razão Social": ["Exemplo de Cliente"],
            "UF": ["SC"],
            "Município": ["Criciúma"],
            "Endereço": ["Rua X"],
            "Número Documento": ["123"],
            "Série": ["1"],
            "Data": ["2024-01-01"],
            "Situação": [0],
            "CFOP": ["5102"],
            "Valor Produtos": [100000.0],
            "Valor Descontos": [0.0],
            "Valor Contábil": [100000.0],
            "Lucro": [20000.0],
            "Chassi": ["ABC123"],
        }
    )

    saida = tmp_path / "relatorio.xlsx"
    codigo_mapa = {"ABC123": "COD123"}
    result = gerar_relatorio_fiscal_excel(df, saida, codigo_por_chassi=codigo_mapa)

    assert saida.exists(), "Arquivo Excel não foi criado"
    assert result.loc[0, "Base de Calculo ICMS"] == 5000.0
    assert result.loc[0, "Valor ICMS"] == 5000.0 * 0.19
    assert result.loc[0, "Base de Calculo PIS/COFINS"] == 20000.0
    assert result.loc[0, "Valor PIS"] == 20000.0 * 0.0065
    assert result.loc[0, "Valor COFINS"] == 20000.0 * 0.03
    assert result.loc[0, "Acumulador"] == 3
    assert result.loc[0, "Código do Item"] == "COD123"
