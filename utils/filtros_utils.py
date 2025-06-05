
import pandas as pd

def obter_anos_meses_unicos(df, coluna_data):
    """Retorna listas de anos e meses existentes em ``coluna_data``."""
    if coluna_data not in df.columns:
        return [], []

    datas = pd.to_datetime(df[coluna_data], errors="coerce").dropna()
    anos = sorted(datas.dt.year.unique())
    meses = sorted(datas.dt.month.unique())
    return anos, meses

def aplicar_filtro_periodo(df, coluna_data, ano=None, mes=None):
    """Filtra ``df`` pelo ano e mês informados na coluna de data fornecida."""
    if coluna_data not in df.columns:
        return df

    df = df.copy()
    df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce")

    if ano is not None:
        df = df[df[coluna_data].dt.year == int(ano)]
    if mes is not None:
        df = df[df[coluna_data].dt.month == int(mes)]

    return df
