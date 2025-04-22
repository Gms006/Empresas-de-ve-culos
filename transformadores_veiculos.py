import pandas as pd
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Carregar regras de classificação de produto
with open('classificacao_produto.json', encoding='utf-8') as f:
    CLASSIFICACAO_PRODUTO = json.load(f)

BLACKLIST = CLASSIFICACAO_PRODUTO.get("blacklist", [])
KEYWORDS_VEICULO = CLASSIFICACAO_PRODUTO.get("keywords_veiculo", [])

def verificar_produto_valido(produto):
    if not produto:
        return False
    produto_lower = produto.lower()
    if any(palavra in produto_lower for palavra in BLACKLIST):
        return False
    if any(keyword in produto_lower for keyword in KEYWORDS_VEICULO):
        return True
    return False

def gerar_estoque_fiscal(df_entrada, df_saida):
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    # Criar chave de identificação
    for col in ['Chassi', 'Placa']:
        if col not in df_entrada.columns:
            df_entrada[col] = ''
        if col not in df_saida.columns:
            df_saida[col] = ''

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('') + df_entrada['Placa'].fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna('') + df_saida['Placa'].fillna('')

    df_saida = df_saida.drop_duplicates(subset='Chave')
    df_estoque = pd.merge(df_entrada, df_saida, on='Chave', how='left', suffixes=('_entrada', '_saida'))

    df_estoque['Situação'] = df_estoque['Data Saída'].notna().map({True: 'Vendido', False: 'Em Estoque'})

    # Calcular Lucro
    df_estoque['Valor Entrada'] = pd.to_numeric(df_estoque.get('Valor Total_entrada'), errors='coerce')
    df_estoque['Valor Venda'] = pd.to_numeric(df_estoque.get('Valor Total_saida'), errors='coerce')
    df_estoque['Lucro'] = df_estoque['Valor Venda'].fillna(0) - df_estoque['Valor Entrada'].fillna(0)

    return df_estoque

def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('') + df_entrada['Placa'].fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna('') + df_saida['Placa'].fillna('')

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        if verificar_produto_valido(row.get('Produto')):
            erros.append({'Tipo': 'Entrada', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_ENTRADA'})

    for _, row in duplicadas_saida.iterrows():
        if verificar_produto_valido(row.get('Produto')):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_SAIDA'})

    return pd.DataFrame(erros)

def gerar_kpis(df_estoque):
    return {
        "Total Vendido (R$)": df_estoque[df_estoque['Situação'] == 'Vendido']['Valor Venda'].sum(),
        "Lucro Total (R$)": df_estoque['Lucro'].sum(),
        "Estoque Atual (R$)": df_estoque[df_estoque['Situação'] == 'Em Estoque']['Valor Entrada'].sum()
    }

def gerar_resumo_mensal(df_estoque):
    df = df_estoque[df_estoque['Situação'] == 'Vendido'].copy()
    df['Mês'] = pd.to_datetime(df['Data Saída'], errors='coerce').dt.to_period("M").dt.start_time
    resumo = df.groupby('Mês').agg({'Valor Entrada': 'sum', 'Valor Venda': 'sum', 'Lucro': 'sum'}).reset_index()
    return resumo
