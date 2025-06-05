import pandas as pd
import json
import logging
import os
import re

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
def _limpar_chave(valor: str) -> str:
    """Remove caracteres não alfanuméricos e aplica caixa alta."""
    if valor is None:
        return ""
    return re.sub(r"\W", "", str(valor)).upper()


def gerar_estoque_fiscal(df_entrada, df_saida):
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    if 'Tipo Produto' in df_entrada.columns:
        df_entrada = df_entrada[df_entrada['Tipo Produto'] == 'Veículo']
    if 'Tipo Produto' in df_saida.columns:
        df_saida = df_saida[df_saida['Tipo Produto'] == 'Veículo']

    # Manter apenas itens classificados como Veículo
    if "Tipo Produto" in df_entrada.columns:
        df_entrada = df_entrada[df_entrada["Tipo Produto"] == "Veículo"].copy()
    if "Tipo Produto" in df_saida.columns:
        df_saida = df_saida[df_saida["Tipo Produto"] == "Veículo"].copy()

    # Utilizar o chassi como chave de rastreamento principal. Caso o chassi não
    # esteja disponível, utiliza-se a placa apenas como apoio.
    df_entrada['Chave'] = df_entrada['Chassi'].apply(_limpar_chave)
    df_saida['Chave'] = df_saida['Chassi'].apply(_limpar_chave)

    df_entrada.loc[df_entrada['Chave'] == '', 'Chave'] = (
        df_entrada['Placa'].apply(_limpar_chave)
    )
    df_saida.loc[df_saida['Chave'] == '', 'Chave'] = (
        df_saida['Placa'].apply(_limpar_chave)
    )

    merge_cols = ['Chave']
    if 'Empresa CNPJ' in df_entrada.columns and 'Empresa CNPJ' in df_saida.columns:
        merge_cols.append('Empresa CNPJ')

    # Remover duplicidades explícitas de saída para evitar múltiplas associações
    df_saida = df_saida.drop_duplicates(subset=merge_cols)

    # Usar junção externa para identificar saídas sem entradas
    df_estoque = pd.merge(
        df_entrada,
        df_saida,
        on=merge_cols,
        how='outer',
        suffixes=('_entrada', '_saida'),
        indicator=True,
    )

    # Classificação do status do veículo
    def classificar_status(merge_flag):
        if merge_flag == 'both':
            return 'Vendido'
        elif merge_flag == 'left_only':
            return 'Em Estoque'
        return 'Erro'

    df_estoque['Situação'] = df_estoque['_merge'].apply(classificar_status)

    # Renomear coluna de data de saída, se existir
    if 'Data Emissão_saida' in df_estoque.columns:
        df_estoque.rename(columns={'Data Emissão_saida': 'Data Saída'}, inplace=True)
    else:
        df_estoque['Data Saída'] = pd.NaT

    df_estoque['Valor Entrada'] = pd.to_numeric(df_estoque.get('Valor Total_entrada'), errors='coerce').fillna(0)
    df_estoque['Valor Venda'] = pd.to_numeric(df_estoque.get('Valor Total_saida'), errors='coerce').fillna(0)
    df_estoque['Lucro'] = df_estoque['Valor Venda'] - df_estoque['Valor Entrada']

    if 'Data Emissão_entrada' in df_estoque.columns:
        df_estoque['Mês Entrada'] = pd.to_datetime(
            df_estoque['Data Emissão_entrada'], errors='coerce'
        ).dt.to_period('M').dt.start_time
    if 'Data Saída' in df_estoque.columns:
        df_estoque['Mês Saída'] = pd.to_datetime(
            df_estoque['Data Saída'], errors='coerce'
        ).dt.to_period('M').dt.start_time

    # Coluna base para filtros
    df_estoque['Data Base'] = df_estoque['Data Saída'].combine_first(
        df_estoque.get('Data Emissão_entrada')
    )
    df_estoque['Mês Base'] = pd.to_datetime(
        df_estoque['Data Base'], errors='coerce'
    ).dt.to_period('M').dt.start_time

    return df_estoque

# Gerar Alertas de Auditoria
def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].apply(_limpar_chave)
    df_saida['Chave'] = df_saida['Chassi'].apply(_limpar_chave)

    df_entrada.loc[df_entrada['Chave'] == '', 'Chave'] = (
        df_entrada['Placa'].apply(_limpar_chave)
    )
    df_saida.loc[df_saida['Chave'] == '', 'Chave'] = (
        df_saida['Placa'].apply(_limpar_chave)
    )

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Entrada', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_ENTRADA'})

    for _, row in duplicadas_saida.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_SAIDA'})

    # Saída sem correspondente na entrada
    chaves_entrada = set(df_entrada['Chave'])
    saidas_sem_entrada = df_saida[~df_saida['Chave'].isin(chaves_entrada)]

    for _, row in saidas_sem_entrada.iterrows():
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
    # Usar o mês base calculado no estoque
    base_col = 'Mês Base' if 'Mês Base' in df.columns else 'Mês Saída'
    df['Mês Resumo'] = df[base_col].fillna(df.get('Mês Entrada'))
    resumo = (
        df.groupby(['Empresa CNPJ', 'Mês Resumo'])
        .agg({'Valor Entrada': 'sum', 'Valor Venda': 'sum', 'Lucro': 'sum'})
        .reset_index()
        .rename(columns={'Mês Resumo': 'Mês'})
    )
    return resumo
