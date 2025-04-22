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

    # Ajustar tipos conforme o layout (reforço)
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

    # Ordenar colunas conforme o layout, evitando duplicidade
    colunas_ordenadas = [col for col, _ in sorted(LAYOUT_COLUNAS.items(), key=lambda x: x[1]['ordem']) if col in df.columns]

    # Adicionar 'Tipo Nota' apenas se necessário
    if 'Tipo Nota' in df.columns and 'Tipo Nota' not in colunas_ordenadas:
        colunas_ordenadas.append('Tipo Nota')

    df = df[colunas_ordenadas]

    return df
