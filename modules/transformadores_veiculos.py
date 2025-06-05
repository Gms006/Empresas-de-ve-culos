import pandas as pd
import json
import logging
import os

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Definir caminho correto para a pasta de configuração
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Carregar regras de classificação de produto
with open(os.path.join(CONFIG_PATH, 'classificacao_produto.json'), encoding='utf-8') as f:
    CLASSIFICACAO_PRODUTO = json.load(f)

BLACKLIST = CLASSIFICACAO_PRODUTO.get("blacklist", [])
KEYWORDS_VEICULO = CLASSIFICACAO_PRODUTO.get("veiculo_keywords", [])

# Função para validar se o produto é um veículo
def verificar_produto_valido(produto):
    if not produto:
        return False
    produto_upper = produto.upper()
    if any(palavra in produto_upper for palavra in BLACKLIST):
        return False
    if any(keyword in produto_upper for keyword in KEYWORDS_VEICULO):
        return True
    return False

# Gerar Estoque Fiscal
def gerar_estoque_fiscal(df_entrada, df_saida):
    """Concilia notas de entrada e saída e classifica o status do veículo.

    A correspondência é feita pelo chassi e, quando disponível, pelo CNPJ da
    empresa. Veículos sem nota de entrada correspondente são sinalizados como
    ``Erro``.
    """

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    # Normalizar chassi e filtrar apenas registros com chassi informado
    df_entrada['Chassi'] = df_entrada['Chassi'].str.upper()
    df_saida['Chassi'] = df_saida['Chassi'].str.upper()

    df_entrada = df_entrada[df_entrada['Chassi'].notna()]
    df_saida = df_saida[df_saida['Chassi'].notna()]

    df_entrada.rename(columns={'Data Emissão': 'Data Entrada'}, inplace=True)
    df_saida.rename(columns={'Data Emissão': 'Data Saída'}, inplace=True)

    merge_cols = ['Chassi']
    if 'Empresa CNPJ' in df_entrada.columns and 'Empresa CNPJ' in df_saida.columns:
        merge_cols.append('Empresa CNPJ')

    df_entrada = df_entrada.drop_duplicates(subset=merge_cols)
    df_saida = df_saida.drop_duplicates(subset=merge_cols)

    df_estoque = pd.merge(
        df_entrada,
        df_saida,
        on=merge_cols,
        how='outer',
        suffixes=('_entrada', '_saida'),
    )

    df_estoque['Situação'] = 'Erro'
    df_estoque.loc[
        df_estoque['Data Entrada'].notna() & df_estoque['Data Saída'].notna(),
        'Situação',
    ] = 'Vendido'
    df_estoque.loc[
        df_estoque['Data Entrada'].notna() & df_estoque['Data Saída'].isna(),
        'Situação',
    ] = 'Em Estoque'

    df_estoque['Valor Entrada'] = pd.to_numeric(
        df_estoque.get('Valor Total_entrada'), errors='coerce'
    ).fillna(0)
    df_estoque['Valor Venda'] = pd.to_numeric(
        df_estoque.get('Valor Total_saida'), errors='coerce'
    ).fillna(0)
    df_estoque['Lucro'] = df_estoque['Valor Venda'] - df_estoque['Valor Entrada']

    df_estoque['Mês Entrada'] = pd.to_datetime(
        df_estoque['Data Entrada'], errors='coerce'
    ).dt.to_period('M').dt.start_time
    df_estoque['Mês Saída'] = pd.to_datetime(
        df_estoque['Data Saída'], errors='coerce'
    ).dt.to_period('M').dt.start_time

    return df_estoque

# Gerar Alertas de Auditoria
def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna('')

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Entrada', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_ENTRADA'})

    for _, row in duplicadas_saida.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_SAIDA'})

    # Saídas sem entradas correspondentes
    chassi_entrada = set(df_entrada['Chave'])
    sem_entrada = df_saida[~df_saida['Chave'].isin(chassi_entrada)]
    for _, row in sem_entrada.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'SAIDA_SEM_ENTRADA'})

    return pd.DataFrame(erros)

# Gerar KPIs
def gerar_kpis(df_estoque):
    return {
        "Total Vendido (R$)": df_estoque[df_estoque['Situação'] == 'Vendido']['Valor Venda'].sum(),
        "Lucro Total (R$)": df_estoque['Lucro'].sum(),
        "Estoque Atual (R$)": df_estoque[df_estoque['Situação'] == 'Em Estoque']['Valor Entrada'].sum()
    }

# Gerar Resumo Mensal
def gerar_resumo_mensal(df_estoque):
    df = df_estoque.copy()
    df['Mês Resumo'] = df['Mês Saída'].fillna(df['Mês Entrada'])
    resumo = (
        df.groupby(['Empresa CNPJ', 'Mês Resumo'])
        .agg({'Valor Entrada': 'sum', 'Valor Venda': 'sum', 'Lucro': 'sum'})
        .reset_index()
        .rename(columns={'Mês Resumo': 'Mês'})
    )
    return resumo
