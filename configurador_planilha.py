import pandas as pd
import json

with open('formato_colunas.json', encoding='utf-8') as f:
    FORMATO_COLUNAS = json.load(f)

with open('ordem_colunas.json', encoding='utf-8') as f:
    ORDEM_COLUNAS = json.load(f)

def configurar_planilha(df):
    # Aplicar tipos
    for col, tipo in FORMATO_COLUNAS.items():
        if col in df.columns:
            if tipo == "float":
                df[col] = pd.to_numeric(df[col], errors='coerce')
            elif tipo == "int":
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            elif tipo == "date":
                df[col] = pd.to_datetime(df[col], errors='coerce')
            else:
                df[col] = df[col].astype(str)

    # Reordenar colunas
    colunas_ordenadas = [col for col in ORDEM_COLUNAS if col in df.columns]
    df = df[colunas_ordenadas]

    return df
