import pandas as pd
import json

with open('layout_colunas.json', encoding='utf-8') as f:
    LAYOUT_COLUNAS = json.load(f)

def configurar_planilha(df):
    df = df.copy()

    print(f"[CONFIGURADOR] Colunas iniciais: {list(df.columns)}")

    for coluna in LAYOUT_COLUNAS.keys():
        if coluna not in df.columns:
            df[coluna] = None

    for coluna, config in LAYOUT_COLUNAS.items():
        tipo = config.get("tipo")
        if coluna in df.columns:
            if tipo == "float":
                df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
            elif tipo == "int":
                df[coluna] = pd.to_numeric(df[coluna], errors='coerce').fillna(0).astype(int)
            elif tipo == "date":
                df[coluna] = pd.to_datetime(df[coluna], errors='coerce')
            else:
                df[coluna] = df[coluna].astype(str)

    colunas_ordenadas = [col for col, _ in sorted(LAYOUT_COLUNAS.items(), key=lambda x: x[1]['ordem']) if col in df.columns]

    if 'Tipo Nota' in df.columns and 'Tipo Nota' not in colunas_ordenadas:
        colunas_ordenadas.append('Tipo Nota')

    df = df[colunas_ordenadas]

    if df.columns.duplicated().any():
        print("[ALERTA] Colunas duplicadas detectadas! Removendo...")
        print(f"Antes: {list(df.columns)}")

    df = df.loc[:, ~df.columns.duplicated()]

    print(f"[CONFIGURADOR] Colunas finais: {list(df.columns)}")

    return df
