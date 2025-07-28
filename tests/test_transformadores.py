import pandas as pd
from modules.transformadores_veiculos import gerar_estoque_fiscal


def test_gerar_estoque_fiscal_uses_valor_item():
    df_entrada = pd.DataFrame({
        'Chassi': ['ABC123'],
        'Placa': ['AAA1234'],
        'Valor Item': [100.0],
        'Data Emissão': [pd.Timestamp('2023-01-01')],
        'Tipo Produto': ['Veículo'],
    })
    df_saida = pd.DataFrame({
        'Chassi': ['ABC123'],
        'Placa': ['AAA1234'],
        'Valor Item': [120.0],
        'Data Emissão': [pd.Timestamp('2023-01-10')],
        'Tipo Produto': ['Veículo'],
    })

    df = gerar_estoque_fiscal(df_entrada, df_saida)
    assert df.loc[0, 'Valor Entrada'] == 100.0
    assert df.loc[0, 'Valor Venda'] == 120.0
