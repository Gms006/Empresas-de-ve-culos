import pandas as pd
import json

# Carregar Layout de Colunas
with open('layout_colunas.json', encoding='utf-8') as f:
    LAYOUT_COLUNAS = json.load(f)

def configurar_planilha(df):
    df = df.copy()

    # Garantir que todas as colunas do layout existam
    for coluna in LAYOUT_COLUNAS.keys():
        if coluna not in df.columns:
            df[coluna] = None

    # Ajustar tipos novamente se necessário (reforço)
    for coluna, config in LAYOUT_COLUNAS.items():
        tipo = config.get("tipo")
        if tipo == "float":
            df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
        elif tipo == "int":
            df[coluna] = pd.to_numeric(df[coluna], errors='coerce').fillna(0).astype(int)
        elif tipo == "date":
            df[coluna] = pd.to_datetime(df[coluna], errors='coerce')
        else:
            df[coluna] = df[coluna].astype(str)

    # Ordenar colunas conforme o layout
    colunas_ordenadas = sorted(LAYOUT_COLUNAS.items(), key=lambda x: x[1]['ordem'])
    df = df[[col for col, _ in colunas_ordenadas if col in df.columns] + ['Tipo Nota']]

    return df
