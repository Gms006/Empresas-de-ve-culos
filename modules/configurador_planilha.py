import pandas as pd
import json
import os

# Caminho para a pasta de configurações
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Carregar Configuração
with open(os.path.join(CONFIG_PATH, 'layout_colunas.json'), encoding='utf-8') as f:
    LAYOUT = json.load(f)

def configurar_planilha(df):
    # Garantir todas as colunas do layout
    for col in LAYOUT.keys():
        if col not in df.columns:
            df[col] = None

    # Aplicar Tipagem
    for col, props in LAYOUT.items():
        tipo = props["tipo"]
        if col in df.columns:
            if tipo == "float":
                df[col] = pd.to_numeric(df[col], errors='coerce')
            elif tipo == "int":
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            elif tipo == "date":
                df[col] = pd.to_datetime(df[col], errors='coerce')
            else:
                df[col] = df[col].astype(str)

    # Ordenar colunas conforme 'ordem'
    ordenadas = sorted(LAYOUT.items(), key=lambda x: x[1]['ordem'])
    colunas_finais = [col for col, _ in ordenadas]

    # Manter colunas adicionais no final
    extras = [col for col in df.columns if col not in colunas_finais]
    df = df[colunas_finais + extras]

    return df
