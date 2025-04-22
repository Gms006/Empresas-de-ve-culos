import pandas as pd

def obter_anos_meses_unicos(df, coluna_data):
    datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
    anos = sorted(datas.dt.year.unique())
    meses = sorted(datas.dt.month.unique())
    return anos, meses

def aplicar_filtro_periodo(df, coluna_data, ano=None, mes=None):
    df = df.copy()
    df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce")
    if ano:
        df = df[df[coluna_data].dt.year == ano]
    if mes:
        df = df[df[coluna_data].dt.month == mes]
    return df
