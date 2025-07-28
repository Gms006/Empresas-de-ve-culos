import pandas as pd
import json
import os

# Caminho para a pasta de configurações
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Carregar Configuração com fallback
try:
    with open(os.path.join(CONFIG_PATH, 'layout_colunas.json'), encoding='utf-8') as f:
        LAYOUT = json.load(f)
except Exception:
    # Define um layout padrao caso ocorra erro na leitura
    LAYOUT = {
        "CFOP": {"tipo": "str", "ordem": 1},
        "Data Emissão": {"tipo": "date", "ordem": 2},
        "Valor Total": {"tipo": "float", "ordem": 3},
        "Emitente Nome": {"tipo": "str", "ordem": 4},
        "Destinatário Nome": {"tipo": "str", "ordem": 5},
        "Destinatário CNPJ": {"tipo": "str", "ordem": 6},
        "Destinatário CPF": {"tipo": "str", "ordem": 7},
        "Chassi": {"tipo": "str", "ordem": 8},
        "Placa": {"tipo": "str", "ordem": 9},
        "Renavam": {"tipo": "str", "ordem": 10},
        "KM": {"tipo": "int", "ordem": 11},
        "Ano Modelo": {"tipo": "int", "ordem": 12},
        "Ano Fabricação": {"tipo": "int", "ordem": 13},
        "Cor": {"tipo": "str", "ordem": 14},
        "Natureza Operação": {"tipo": "str", "ordem": 15},
        "CHAVE XML": {"tipo": "str", "ordem": 16},
    }

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
