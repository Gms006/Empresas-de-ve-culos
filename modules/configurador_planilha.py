import pandas as pd
import json
import os
import logging

# Caminho para a pasta de configurações
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Logger
log = logging.getLogger(__name__)

# Carregar Configuração com fallback
try:
    with open(os.path.join(CONFIG_PATH, 'layout_colunas.json'), encoding='utf-8') as f:
        LAYOUT = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as exc:
    log.warning(f"Falha ao carregar layout_colunas.json: {exc}")
    # Define um layout padrao caso ocorra erro na leitura
    LAYOUT = {
        "CFOP": {"tipo": "str", "ordem": 1},
        "Data Emissão": {"tipo": "date", "ordem": 2},
        "Emitente CNPJ/CPF": {"tipo": "str", "ordem": 3},
        "Destinatário CNPJ/CPF": {"tipo": "str", "ordem": 4},
        "Chassi": {"tipo": "str", "ordem": 5},
        "Placa": {"tipo": "str", "ordem": 6},
        "Produto": {"tipo": "str", "ordem": 7},
        "Valor Total": {"tipo": "float", "ordem": 8},
        "Renavam": {"tipo": "str", "ordem": 9},
        "KM": {"tipo": "int", "ordem": 10},
        "Ano Modelo": {"tipo": "int", "ordem": 11},
        "Ano Fabricação": {"tipo": "int", "ordem": 12},
        "Cor": {"tipo": "str", "ordem": 13},
        "ICMS Alíquota": {"tipo": "float", "ordem": 14},
        "ICMS Valor": {"tipo": "float", "ordem": 15},
        "ICMS Base": {"tipo": "float", "ordem": 16},
        "CST ICMS": {"tipo": "str", "ordem": 17},
        "Redução BC": {"tipo": "float", "ordem": 18},
        "Modalidade BC": {"tipo": "str", "ordem": 19},
        "Natureza Operação": {"tipo": "str", "ordem": 99},
        "CHAVE XML": {"tipo": "str", "ordem": 100},
    }

def configurar_planilha(df):
    # Garantir todas as colunas do layout
    for col in LAYOUT.keys():
        if col not in df.columns:
            df[col] = None

    # Aplicar Tipagem com logs de conversão
    for col, props in LAYOUT.items():
        tipo = props["tipo"]
        if col in df.columns:
            serie = df[col]
            antes_na = serie.isna().sum()
            if tipo == "float":
                convertido = pd.to_numeric(serie, errors='coerce')
            elif tipo == "int":
                convertido = pd.to_numeric(serie, errors='coerce')
                convertido = convertido.astype('Int64')
            elif tipo == "date":
                convertido = pd.to_datetime(serie, errors='coerce')
            else:
                convertido = serie.astype(str)
            depois_na = convertido.isna().sum()
            coercoes = max(0, depois_na - antes_na)
            if coercoes:
                log.warning(
                    f"{coercoes} valores inválidos convertidos para NaN na coluna {col}"
                )
            df[col] = convertido

    # Ordenar colunas conforme 'ordem'
    ordenadas = sorted(LAYOUT.items(), key=lambda x: x[1]['ordem'])
    colunas_finais = [col for col, _ in ordenadas]

    # Manter colunas adicionais no final
    extras = [col for col in df.columns if col not in colunas_finais]
    df = df[colunas_finais + extras]

    return df
