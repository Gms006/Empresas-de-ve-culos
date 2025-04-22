import pandas as pd
import json

with open('layout_colunas.json', encoding='utf-8') as f:
    LAYOUT_COLUNAS = json.load(f)

def configurar_planilha(df):
    df = df.copy()

    # Aplicar tipos
    for col, props in LAYOUT_COLUNAS.items():
        if col in df.columns:
            tipo = props["tipo"]
            if tipo == "float":
                df[col] = pd.to_numeric(df[col], errors='coerce')
            elif tipo == "int":
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            elif tipo == "date":
                df[col] = pd.to_datetime(df[col], errors='coerce')
            else:
                df[col] = df[col].astype(str)

    # Reordenar mantendo colunas adicionais
    ordem = sorted(LAYOUT_COLUNAS.items(), key=lambda x: x[1]["ordem"])
    colunas_ordenadas = [col for col, _ in ordem if col in df.columns]
    colunas_restantes = [col for col in df.columns if col not in colunas_ordenadas]

    df = df[colunas_ordenadas + colunas_restantes]
    return df
